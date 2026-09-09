"""Owner CLI for the bounded executive bridge. Uses DATABASE_URL; never prints it."""
import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from .executive import export_packet, import_review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["review-export", "review-import", "outreach-status", "outreach-reserve", "outreach-authorize", "outreach-complete", "outreach-backfill", "outreach-reconcile", "operator-export", "operator-enqueue", "operator-claim", "operator-complete", "operator-state", "operator-assess", "operator-monitor", "operator-monitor-start", "community-record", "community-export", "prospect-link", "prospect-history", "email-queue", "email-status", "email-suppress"])
    parser.add_argument("--file")
    parser.add_argument("--model", default="codex")
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--latency-ms", type=int)
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.action.startswith(("prospect-", "email-")):
            from . import identity, outreach_email
            payload = json.loads(Path(args.file).read_text(encoding="utf-8-sig")) if args.file else {}
            if args.action == "prospect-link":
                result = identity.link_merchant(db, payload)
            elif args.action == "prospect-history":
                result = identity.merchant_view(db, payload["identity"])
            elif args.action == "email-queue":
                result = outreach_email.queue_email(db, payload)
            elif args.action == "email-suppress":
                outreach_email.suppress(db, payload["recipient"], payload.get("reason", "owner_suppression"), "owner_operator")
                result = {"suppressed": True}
            else:
                result = outreach_email.metrics(db)
            db.commit()
        elif args.action.startswith("community-"):
            from . import community
            if args.action == "community-record":
                if not args.file:
                    parser.error("community-record requires --file")
                payload = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
                result = community.retain(db, payload)
                db.commit()
            else:
                result = community.export(db)
        elif args.action.startswith("operator-"):
            from .operator import operator_action
            payload = json.loads(Path(args.file).read_text(encoding="utf-8-sig")) if args.file else {}
            result = operator_action(db, args.action, payload)
            db.commit()
        elif args.action.startswith("outreach-"):
            from .outbound import operator_action
            from .models import FirstContact
            FirstContact.__table__.create(db.get_bind(), checkfirst=True)
            payload = json.loads(Path(args.file).read_text(encoding="utf-8-sig")) if args.file else {}
            result = operator_action(db, args.action, payload)
            db.commit()
        elif args.action == "review-export":
            result = export_packet(db)
        else:
            if not args.file:
                parser.error("review-import requires --file")
            result = import_review(db, json.loads(Path(args.file).read_text(encoding="utf-8-sig")), model=args.model,
                input_tokens=args.input_tokens, output_tokens=args.output_tokens, latency_ms=args.latency_ms)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
