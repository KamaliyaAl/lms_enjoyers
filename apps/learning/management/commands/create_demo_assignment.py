from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from django.contrib.auth import get_user_model

from courses.models import Course, Assignment, CourseTeacher
from courses.constants import AssignmentStatus, AssigneeMode
from learning.models import (
    StudentAssignment,
    AssignmentComment,
    AssignmentSubmissionTypes,
)
from learning.services.assignment_service import AssignmentService
from learning.tasks import update_student_assignment_stats


class Command(BaseCommand):
    help = (
        "Create an assignment in a course and perform all follow-up actions: "
        "generate StudentAssignment records for enrolled students and synchronously "
        "recalculate stats so that the assignment appears immediately in student UI. "
        "Optionally, seed a review item (assign teacher and create a test SOLUTION from a student)."
    )

    def add_arguments(self, parser):
        course_group = parser.add_mutually_exclusive_group(required=True)
        course_group.add_argument("--course-id", type=int, dest="course_id")
        course_group.add_argument("--course-name", type=str, dest="course_name")

        parser.add_argument("--title", required=True, help="Assignment title")
        parser.add_argument(
            "--deadline",
            required=True,
            help="Deadline in 'YYYY-MM-DD HH:MM' (interpreted in UTC)",
        )
        parser.add_argument(
            "--submission-type",
            default="online",
            choices=("online", "offline"),
            help="Submission type (default: online)",
        )
        parser.add_argument(
            "--max-score", type=int, default=10, help="Maximum score (default: 10)"
        )
        parser.add_argument(
            "--weight",
            type=str,
            default="1.00",
            help="Assignment weight as decimal string (default: 1.00)",
        )

        # Optional seeding of review queue
        parser.add_argument(
            "--seed-review",
            action="store_true",
            help="Also seed a review item (assign teacher and create a test SOLUTION)",
        )
        parser.add_argument(
            "--student-username",
            type=str,
            help="Username of student to create a test SOLUTION from (used with --seed-review)",
        )
        parser.add_argument(
            "--teacher-username",
            type=str,
            help="Username of teacher to assign as reviewer (used with --seed-review)",
        )

    def handle(self, *args, **options):
        course: Optional[Course] = None
        if options.get("course_id") is not None:
            course = Course.objects.filter(pk=options["course_id"]).first()
        else:
            course = (
                Course.objects.filter(meta_course__name=options["course_name"])\
                .order_by("-id").first()
            )
        if not course:
            raise CommandError("Course not found by given identifier")

        title = options["title"].strip()
        try:
            deadline_dt = datetime.strptime(options["deadline"], "%Y-%m-%d %H:%M")
        except ValueError:
            raise CommandError("Invalid --deadline format. Use 'YYYY-MM-DD HH:MM'.")
        deadline_utc = timezone.make_aware(deadline_dt, timezone.utc)

        submission_type = options["submission_type"]
        max_score = int(options["max_score"]) if options["max_score"] else 10
        try:
            weight = Decimal(options["weight"])
        except Exception as e:
            raise CommandError(f"Invalid --weight value: {e}")

        # Determine assignment timezone from course main branch (fallback to UTC)
        tz_name = getattr(getattr(course, 'main_branch', None), 'time_zone', 'UTC')

        # Create or get assignment
        assignment, created = Assignment.objects.get_or_create(
            course=course,
            title=title,
            defaults={
                "text": "Seeded assignment",
                "deadline_at": deadline_utc,
                "maximum_score": max_score,
                "weight": weight,
                "submission_type": submission_type,
                "time_zone": tz_name,
                "assignee_mode": AssigneeMode.MANUAL,
            },
        )
        if not created:
            # Update key fields if already existed
            assignment.deadline_at = deadline_utc
            assignment.maximum_score = max_score
            assignment.weight = weight
            assignment.submission_type = submission_type
            assignment.time_zone = tz_name
            assignment.assignee_mode = AssigneeMode.MANUAL
            assignment.save(update_fields=[
                "deadline_at", "maximum_score", "weight", "submission_type", "time_zone", "assignee_mode"
            ])

        # Generate StudentAssignment records for all enrolled students
        AssignmentService.bulk_create_student_assignments(assignment)

        # Synchronously recalc stats so student UI shows the assignment immediately
        for sa in StudentAssignment.objects.filter(assignment=assignment).only("id"):
            update_student_assignment_stats(sa.id)

        # Optional: seed a review item
        if options.get("seed_review"):
            student_username = options.get("student_username")
            teacher_username = options.get("teacher_username")
            if not student_username or not teacher_username:
                self.stdout.write(
                    self.style.WARNING(
                        "--seed-review requires both --student-username and --teacher-username. Skipping seeding."
                    )
                )
            else:
                self._seed_review_item(
                    course=course,
                    assignment=assignment,
                    student_username=student_username,
                    teacher_username=teacher_username,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"OK: assignment id={assignment.id} title='{assignment.title}' deadline={assignment.deadline_at.isoformat()} created={created}"
            )
        )

    def _seed_review_item(self, *, course: Course, assignment: Assignment,
                           student_username: str, teacher_username: str) -> None:
        User = get_user_model()
        student = User.objects.filter(username=student_username).first()
        teacher = User.objects.filter(username=teacher_username).first()
        if not student or not teacher:
            self.stdout.write(self.style.WARNING("Student or teacher not found; skipping review seed."))
            return

        # Ensure course teacher link exists and set reviewer flag (BitField API)
        ct, _ = CourseTeacher.objects.get_or_create(course=course, teacher=teacher)
        try:
            # BitField boolean flags
            ct.roles.reviewer = True
            ct.roles.lecturer = True
            ct.save()
        except Exception:
            # Fallback: ignore if bitfield API differs
            pass

        sa = StudentAssignment.objects.filter(assignment=assignment, student=student).first()
        if not sa:
            self.stdout.write(self.style.WARNING("StudentAssignment not found; skipping review seed."))
            return

        sa.assignee = ct
        sa.status = AssignmentStatus.ON_CHECKING
        sa.save(update_fields=["assignee", "status"])

        # Create a published solution if none exists
        solution = AssignmentComment.objects.filter(
            student_assignment=sa, type=AssignmentSubmissionTypes.SOLUTION
        ).first()
        if not solution:
            solution = AssignmentComment.objects.create(
                student_assignment=sa,
                type=AssignmentSubmissionTypes.SOLUTION,
                text="Seeded solution for review",
                author=student,
                is_published=True,
            )
        # Recalc stats for review queue and teacher UI
        update_student_assignment_stats(sa.id)
        self.stdout.write(self.style.SUCCESS(
            f"OK: review seeded sa_id={sa.id} solution_id={solution.id}"
        ))
