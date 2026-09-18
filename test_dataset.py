"""
Test cases for the eval run. Mix of:
 - straightforward questions the KB answers well (test Correctness/Faithfulness)
 - a question needing 2 facts from one doc (tests Completeness)
 - a question with no answer in the KB at all (tests Refusal / Faithfulness --
   does the agent admit it doesn't know, or hallucinate?)
 - a vague/ambiguous question (tests Helpfulness / LogicalCoherence)

Extra fields beyond `query` / `reference_response` are used by local_tests.py
for fast, deterministic checks that don't need an LLM judge or AWS at all:

  expected_doc_id   - which KB doc SHOULD be top of the retrieved list
  required_facts    - substrings that MUST appear somewhere in the answer
  expect_refusal    - True if the correct behavior is "I don't know" (no doc
                      in the KB answers this)
"""

TEST_CASES = [
    {
        "query": "How long until my password expires, and how do I reset it?",
        "reference_response": (
            "Passwords expire after 90 days. You can reset your own password "
            "at any time via the self-service portal at password.corp.internal, "
            "which requires MFA verification."
        ),
        "expected_doc_id": "kb-001",
        "required_facts": ["90 days", "password.corp.internal"],
        "expect_refusal": False,
    },
    {
        "query": "My VPN won't connect, what should I check first?",
        "reference_response": (
            "Check that your local firewall allows outbound UDP 443, then "
            "restart the Cisco AnyConnect service."
        ),
        "expected_doc_id": "kb-002",
        "required_facts": ["UDP 443", "AnyConnect"],
        "expect_refusal": False,
    },
    {
        "query": "What's the name of the guest Wi-Fi network in the office?",
        "reference_response": (
            "The guest Wi-Fi network is called CorpNet-Guest. It does not "
            "require credentials but is rate-limited."
        ),
        "expected_doc_id": "kb-007",
        "required_facts": ["CorpNet-Guest"],
        "expect_refusal": False,
    },
    {
        "query": "I lost my phone, how do I re-enroll in MFA?",
        "reference_response": (
            "Self-service MFA re-enrollment is disabled for security reasons. "
            "You need to contact the IT helpdesk to re-enroll a lost or new "
            "phone in Okta Verify."
        ),
        "expected_doc_id": "kb-005",
        "required_facts": ["helpdesk"],
        "expect_refusal": False,
    },
    {
        "query": "How much annual leave am I entitled to?",
        "reference_response": (
            "This information is not available in the IT helpdesk knowledge "
            "base; the assistant should say it doesn't know rather than "
            "guessing, and suggest contacting HR."
        ),
        "expected_doc_id": None,
        "required_facts": [],
        "expect_refusal": True,
    },
    {
        "query": "Can I get more shared drive storage, and is there a limit?",
        "reference_response": (
            "Yes, additional storage above the default 50GB requires a "
            "business justification and manager sign-off, and is capped at "
            "500GB total."
        ),
        "expected_doc_id": "kb-006",
        "required_facts": ["50GB", "500GB"],
        "expect_refusal": False,
    },
]
