"""Model registry — import order matters for metadata resolution."""

from app.models.application import Application
from app.models.audit import AuditLog
from app.models.base import utcnow
from app.models.company import Company
from app.models.engagement import JobReport, SavedJob, SavedSearch
from app.models.job import Job
from app.models.notification import Notification
from app.models.profile import (
    AuthIdentity,
    Certification,
    Education,
    Language,
    Message,
    MessageThread,
    PortfolioProject,
    Profile,
    Skill,
    UserPrivacySettings,
    WorkExperience,
)
from app.models.user import User

__all__ = [
    "Application",
    "AuditLog",
    "AuthIdentity",
    "Certification",
    "Company",
    "Education",
    "Job",
    "JobReport",
    "Language",
    "Message",
    "MessageThread",
    "Notification",
    "PortfolioProject",
    "Profile",
    "SavedJob",
    "SavedSearch",
    "Skill",
    "User",
    "UserPrivacySettings",
    "WorkExperience",
    "utcnow",
]
