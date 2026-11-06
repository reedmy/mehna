"""Domain enums and their Arabic labels.

Single source of truth for status strings — never compare against literals.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value


class Role(StrEnum):
    SEEKER = "seeker"
    EMPLOYER = "employer"
    ADMIN = "admin"


ROLE_LABELS = {
    Role.SEEKER.value: "باحث عن عمل",
    Role.EMPLOYER.value: "صاحب عمل",
    Role.ADMIN.value: "مدير النظام",
}


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


VERIFICATION_LABELS = {
    VerificationStatus.UNVERIFIED.value: "غير موثّقة",
    VerificationStatus.PENDING.value: "قيد المراجعة",
    VerificationStatus.VERIFIED.value: "موثّقة",
    VerificationStatus.REJECTED.value: "مرفوضة",
}


class JobStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    EXPIRED = "expired"


JOB_STATUS_LABELS = {
    JobStatus.DRAFT.value: "مسودة",
    JobStatus.PUBLISHED.value: "منشورة",
    JobStatus.CLOSED.value: "مغلقة",
    JobStatus.EXPIRED.value: "منتهية",
}


class JobType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    REMOTE = "remote"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


JOB_TYPE_LABELS = {
    JobType.FULL_TIME.value: "دوام كامل",
    JobType.PART_TIME.value: "دوام جزئي",
    JobType.CONTRACT.value: "عقد",
    JobType.REMOTE.value: "عن بُعد",
    JobType.INTERNSHIP.value: "تدريب",
    JobType.FREELANCE.value: "عمل حر",
}


class WorkMode(StrEnum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


WORK_MODE_LABELS = {
    WorkMode.ONSITE.value: "من المكتب",
    WorkMode.REMOTE.value: "عن بُعد",
    WorkMode.HYBRID.value: "هجين",
}


SKILL_LEVEL_LABELS = {
    "beginner": "مبتدئ",
    "intermediate": "متوسط",
    "advanced": "متقدم",
    "expert": "خبير",
}


LANGUAGE_PROFICIENCY_LABELS = {
    "basic": "أساسي",
    "conversational": "محادثة",
    "professional": "مهني",
    "fluent": "بطلاقة",
    "native": "اللغة الأم",
}


EMPLOYMENT_TYPE_LABELS = {
    "full_time": "دوام كامل",
    "part_time": "دوام جزئي",
    "contract": "عقد",
    "internship": "تدريب",
    "freelance": "عمل حر",
}


PROFILE_VISIBILITY_LABELS = {
    "public": "عام — يظهر للجميع",
    "employers": "أصحاب العمل فقط",
    "private": "خاص — أنا فقط",
}


PROFILE_SECTIONS = [
    ("basic", "البيانات الأساسية", "user"),
    ("experience", "الخبرة العملية", "briefcase"),
    ("education", "التعليم", "graduation"),
    ("skills", "المهارات واللغات", "star"),
    ("certifications", "الشهادات والإنجازات", "award"),
    ("projects", "المشاريع والأعمال", "folder"),
    ("privacy", "الخصوصية وملف السيرة", "lock"),
]


class CareerLevel(StrEnum):
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


CAREER_LEVEL_LABELS = {
    CareerLevel.ENTRY.value: "مبتدئ",
    CareerLevel.JUNIOR.value: "حديث التخرج",
    CareerLevel.MID.value: "متوسط الخبرة",
    CareerLevel.SENIOR.value: "خبير",
    CareerLevel.LEAD.value: "قيادي",
}


class ApplicationStatus(StrEnum):
    SUBMITTED = "submitted"
    VIEWED = "viewed"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


APPLICATION_STATUS_LABELS = {
    ApplicationStatus.SUBMITTED.value: "تم الإرسال",
    ApplicationStatus.VIEWED.value: "تمت المشاهدة",
    ApplicationStatus.SHORTLISTED.value: "قائمة مختصرة",
    ApplicationStatus.INTERVIEW.value: "مقابلة",
    ApplicationStatus.ACCEPTED.value: "مقبول",
    ApplicationStatus.REJECTED.value: "مرفوض",
    ApplicationStatus.WITHDRAWN.value: "منسحب",
}

APPLICATION_STATUS_TONE = {
    ApplicationStatus.SUBMITTED.value: "neutral",
    ApplicationStatus.VIEWED.value: "info",
    ApplicationStatus.SHORTLISTED.value: "info",
    ApplicationStatus.INTERVIEW.value: "warning",
    ApplicationStatus.ACCEPTED.value: "success",
    ApplicationStatus.REJECTED.value: "danger",
    ApplicationStatus.WITHDRAWN.value: "neutral",
}


class ReportReason(StrEnum):
    FEE = "asks_for_money"
    FAKE = "fake_job"
    MISLEADING = "misleading"
    INAPPROPRIATE = "inappropriate"
    OTHER = "other"


REPORT_REASON_LABELS = {
    ReportReason.FEE.value: "يطلب مالًا من المتقدم",
    ReportReason.FAKE.value: "وظيفة وهمية",
    ReportReason.MISLEADING.value: "معلومات مضللة",
    ReportReason.INAPPROPRIATE.value: "محتوى غير لائق",
    ReportReason.OTHER.value: "سبب آخر",
}


class ReportStatus(StrEnum):
    OPEN = "open"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class NotificationType(StrEnum):
    APPLICATION_NEW = "application_new"
    APPLICATION_STATUS = "application_status"
    COMPANY_VERIFIED = "company_verified"
    JOB_EXPIRING = "job_expiring"
    SYSTEM = "system"


# ── Iraq-specific option lists (used by forms and filters) ──

CITIES = [
    "بغداد",
    "البصرة",
    "أربيل",
    "الموصل",
    "السليمانية",
    "النجف",
    "كربلاء",
    "كركوك",
    "دهوك",
    "الناصرية",
    "العمارة",
    "الديوانية",
    "الحلة",
    "الكوت",
    "الرمادي",
    "الفلوجة",
    "سامراء",
    "تكريت",
    "زاخو",
    "حلبجة",
    "عن بُعد",
]

INDUSTRIES = [
    "تقنية المعلومات",
    "النفط والغاز",
    "البناء والمقاولات",
    "التجارة والتجزئة",
    "المصارف والمال",
    "الاتصالات",
    "التعليم",
    "الصحة",
    "النقل واللوجستيات",
    "الإعلام والتسويق",
    "المنظمات غير الحكومية",
    "الضيافة والمطاعم",
    "الصناعة",
    "الزراعة",
    "خدمات أخرى",
]

COMPANY_SIZES = [
    ("1-10", "١–١٠ موظفين"),
    ("11-50", "١١–٥٠ موظفًا"),
    ("51-200", "٥١–٢٠٠ موظف"),
    ("201-500", "٢٠١–٥٠٠ موظف"),
    ("500+", "أكثر من ٥٠٠ موظف"),
]
