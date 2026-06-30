"""Built-in text-synthesis skills (deterministic, offline — no LLM).

``summarize_symptoms`` digests free-text customer-care transcripts into a
symptom-type breakdown, filtering out non-network asks (billing, account, …). The
production version is an LLM call; this keyword classifier is the free dev/test
stand-in. The other agent registers an LLM-backed ``summarize_symptoms`` under the
same name to swap it in (see docs/11-ai-panel-builder.md).

# DATA AGENT / LLM AGENT: replace the keyword maps below with the real model call.
"""

from __future__ import annotations

from .registry import skill

# Network symptom types -> trigger phrases (lower-cased substring match). Order is
# the tie-break for ranking; the breakdown is sorted by user count.
_SYMPTOMS: list[tuple[str, tuple[str, ...]]] = [
    ("Dropped calls", ("drop", "dropped", "cut off", "cuts off", "disconnect", "call drops")),
    ("No signal / coverage", ("no signal", "no service", "no bars", "no reception", "no coverage",
                              "dead zone", "dead spot", "can't connect", "cannot connect")),
    ("Can't make/receive calls", ("can't call", "cannot call", "can't make a call", "calls fail",
                                  "failed call", "won't ring", "can't receive call")),
    ("Slow data / internet", ("slow data", "slow internet", "slow speed", "buffering", "won't load",
                              "can't load", "lagging", "slow connection", "data is slow")),
    ("Texting / SMS issues", ("can't text", "cannot text", "sms", "text not", "message won't send",
                              "texts failing", "can't send text")),
]

# Non-network asks to filter out when filter_non_network is set.
_NON_NETWORK = (
    "bill", "billing", "charge", "overcharge", "invoice", "payment", "refund", "autopay",
    "account", "password", "log in", "login", "sign in", "upgrade my plan", "plan price",
    "promo", "discount", "store hours", "device trade", "warranty",
)


def _texts(transcripts):
    """Normalize input to a list of (usid, lower_text). Accepts dicts with
    usid/text (or transcript_text), or (usid, text) pairs."""
    out = []
    for t in transcripts or []:
        if isinstance(t, dict):
            usid = str(t.get("usid") or t.get("USID") or "")
            text = t.get("text") or t.get("transcript_text") or t.get("transcript") or ""
        else:  # (usid, text) tuple/list
            usid, text = str(t[0]), t[1]
        out.append((usid, str(text or "").lower()))
    return out


@skill("summarize_symptoms")
def summarize_symptoms(transcripts, filter_non_network: bool = True):
    """Classify care-call transcripts into network symptom types and count the
    distinct users mentioning each. Returns a dict the transcript panel renders:
    ``{summary, breakdown:[{symptom_type, n_users, n_mentions, share}], n_calls,
    n_users, filtered_out}``."""
    rows = _texts(transcripts)
    n_calls = len(rows)
    users_by_symptom: dict[str, set[str]] = {name: set() for name, _ in _SYMPTOMS}
    mentions: dict[str, int] = {name: 0 for name, _ in _SYMPTOMS}
    network_users: set[str] = set()
    filtered_out = 0

    for usid, text in rows:
        matched = False
        for name, kws in _SYMPTOMS:
            if any(kw in text for kw in kws):
                users_by_symptom[name].add(usid)
                mentions[name] += 1
                network_users.add(usid)
                matched = True
        if not matched and filter_non_network and any(kw in text for kw in _NON_NETWORK):
            filtered_out += 1

    denom = max(1, len(network_users))
    breakdown = [
        {
            "symptom_type": name,
            "n_users": len(users_by_symptom[name]),
            "n_mentions": mentions[name],
            "share": round(len(users_by_symptom[name]) / denom, 3),
        }
        for name, _ in _SYMPTOMS
        if users_by_symptom[name]
    ]
    breakdown.sort(key=lambda b: (b["n_users"], b["n_mentions"]), reverse=True)

    if breakdown:
        top = breakdown[0]
        others = ", ".join(f"{b['symptom_type']} ({b['n_users']})" for b in breakdown[1:3])
        summary = (
            f"Across {n_calls} customer-care calls from {len(network_users)} users with "
            f"network-related complaints, the most common symptom was "
            f"**{top['symptom_type']}** ({top['n_users']} users)."
        )
        if others:
            summary += f" Other notable symptoms: {others}."
        if filter_non_network and filtered_out:
            summary += f" {filtered_out} non-network calls (billing/account) were filtered out."
    else:
        summary = (
            f"No network-related symptoms were found across {n_calls} calls"
            + (f" ({filtered_out} non-network calls filtered out)." if filtered_out else ".")
        )

    return {
        "summary": summary,
        "breakdown": breakdown,
        "n_calls": n_calls,
        "n_users": len(network_users),
        "filtered_out": filtered_out,
    }
