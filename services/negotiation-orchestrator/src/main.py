from autohaggle_shared.negotiation import run_negotiation_strategy


def main() -> None:
    result = run_negotiation_strategy(
        user_name="Sample Buyer",
        target_otd=32000,
        dealer_otd=33900,
        competitor_best_otd=32500,
    )
    print(result)


if __name__ == "__main__":
    main()

