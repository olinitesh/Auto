from typing import TypedDict

from langgraph.graph import END, StateGraph


class NegotiationState(TypedDict):
    user_name: str
    target_otd: float
    dealer_otd: float
    competitor_best_otd: float | None
    offer_rank: int | None
    days_on_market: int | None
    price_drop_30d: float | None
    action: str
    anchor_otd: float
    rationale: str
    response_text: str


DISCLOSURE_PREFIX = "I am an AI assistant representing {user_name}. "


def strategy_node(state: NegotiationState) -> NegotiationState:
    competitor = state.get("competitor_best_otd")
    anchors = [state["target_otd"], state["dealer_otd"]]
    if competitor:
        anchors.append(competitor)
    baseline = min(anchors)

    anchor_otd = round(baseline - 300, 2)
    gap = state["dealer_otd"] - baseline

    signal_parts: list[str] = []
    if state.get("offer_rank"):
        signal_parts.append(f"your quote is currently ranked #{int(state['offer_rank'])} in our shortlist")
    if state.get("days_on_market") is not None:
        signal_parts.append(f"this unit has been on market for {int(state['days_on_market'])} days")
    if state.get("price_drop_30d"):
        signal_parts.append(f"we have seen a 30-day drop of ${float(state['price_drop_30d']):,.0f}")
    evidence_line = f" We are using market signals: {'; '.join(signal_parts)}." if signal_parts else ""

    if gap <= 0:
        action = "accept_candidate"
        rationale = "Dealer is at or below target baseline."
        message = (
            "Thank you for the itemized OTD quote. The numbers are competitive. "
            "Please confirm final availability for same-day signing."
            f"{evidence_line}"
        )
    else:
        action = "counter_offer"
        rationale = "Dealer quote exceeds target baseline."
        message = (
            f"My client is ready to buy today at ${anchor_otd:,.0f} OTD with a full itemized breakdown. "
            "Please remove or justify market adjustments and share your best final offer."
            f"{evidence_line}"
        )

    return {
        **state,
        "action": action,
        "anchor_otd": anchor_otd,
        "rationale": rationale,
        "response_text": DISCLOSURE_PREFIX.format(user_name=state["user_name"]) + message,
    }


def build_graph():
    graph = StateGraph(NegotiationState)
    graph.add_node("strategy", strategy_node)
    graph.set_entry_point("strategy")
    graph.add_edge("strategy", END)
    return graph.compile()


negotiation_graph = build_graph()


def run_negotiation_strategy(
    user_name: str,
    target_otd: float,
    dealer_otd: float,
    competitor_best_otd: float | None = None,
    offer_rank: int | None = None,
    days_on_market: int | None = None,
    price_drop_30d: float | None = None,
) -> NegotiationState:
    state: NegotiationState = {
        "user_name": user_name,
        "target_otd": target_otd,
        "dealer_otd": dealer_otd,
        "competitor_best_otd": competitor_best_otd,
        "offer_rank": offer_rank,
        "days_on_market": days_on_market,
        "price_drop_30d": price_drop_30d,
        "action": "",
        "anchor_otd": 0.0,
        "rationale": "",
        "response_text": "",
    }
    return negotiation_graph.invoke(state)
