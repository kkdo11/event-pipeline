"""이벤트 생성기 CLI 엔트리포인트."""
import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Event log generator")
    parser.add_argument("--rate", type=int, default=50, help="초당 생성 이벤트 수 (기본: 50)")
    parser.add_argument("--duration", type=int, default=60, help="실행 시간 초 (0=무한, 기본: 60)")
    parser.add_argument("--total", type=int, default=0, help="총 생성 건수 (0=제한 없음)")
    parser.add_argument("--seed-heavy", type=int, default=0, metavar="N", help="N건 일괄 시딩 (파티셔닝 벤치용)")
    parser.add_argument("--batch-size", type=int, default=100, help="bulk insert 단위 (기본: 100)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"[generator] rate={args.rate}/s duration={args.duration}s "
          f"total={args.total or '∞'} seed_heavy={args.seed_heavy or '-'}")
    # Step 1.4에서 실제 생성 로직 추가


if __name__ == "__main__":
    main()
