"""Owner review days are Pacific calendar days, not 24-hour UTC buckets."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .models import Evidence

REVIEW_TIMEZONE = ZoneInfo("America/Los_Angeles")


@dataclass(frozen=True)
class ReviewDay:
    day: str
    start: float
    due: float
    end: float
    next_due: float

    @property
    def key(self):
        return "pacific:" + self.day


def review_day(now):
    day = datetime.fromtimestamp(now, REVIEW_TIMEZONE).date()
    tomorrow = day + timedelta(days=1)
    def at(date, hour):
        return datetime.combine(date, time(hour), REVIEW_TIMEZONE).timestamp()
    return ReviewDay(day.isoformat(), at(day, 0), at(day, 9), at(tomorrow, 0), at(tomorrow, 9))


def completed_review(db, window):
    # Include historical UTC-keyed reviews without rewriting their audit records.
    return db.scalar(select(Evidence).where(Evidence.kind == "EXECUTIVE_REVIEW",
        Evidence.subject == "mission", Evidence.occurred_at >= window.start,
        Evidence.occurred_at < window.end).order_by(Evidence.occurred_at, Evidence.id).limit(1))
