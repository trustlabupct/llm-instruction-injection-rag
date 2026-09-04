"""Tests for retrieval (rag_pipeline) and prompt construction (prompts)."""
import prompts
from rag_pipeline import Retriever, load_documents, load_queries


def test_corpus_composition():
    docs = load_documents()
    assert len(docs) == 40
    assert sum(d.is_poisoned for d in docs) == 16
    fams = {d.attack_family for d in docs if d.is_poisoned}
    assert fams == {"instruction_override", "context_contamination", "tool_abuse", "data_exfiltration"}


def test_queries_metadata():
    qs = load_queries()
    assert len(qs) == 32
    for q in qs:
        assert isinstance(q["allowed_tools"], list)
        assert isinstance(q["forbidden_tools"], list)


def test_retriever_retrieves_relevant_doc():
    r = Retriever(load_documents(), backend="tfidf")
    res = r.retrieve("What requirements do I need for internships?", top_k=3)
    assert len(res) == 3
    # the clean internships document (D005) should be among the retrieved ones
    assert any(d.doc_id == "D005" for d, _ in res)
    # scores come sorted from highest to lowest
    scores = [s for _, s in res]
    assert scores == sorted(scores, reverse=True)


def test_configurations_and_filter():
    assert prompts.CONFIGURATIONS == ["C1", "C2", "C3", "C4", "C5"]
    assert prompts.TOOLS_ENABLED["C1"] is False
    assert prompts.OUTPUT_FILTER["C5"] is True
    assert all(prompts.OUTPUT_FILTER[c] is False for c in ["C1", "C2", "C3", "C4"])


def test_build_prompt_separates_sources_in_c3_c5():
    docs = load_documents()[:3]
    retrieved = [(d, 0.5) for d in docs]
    sys_c2, user_c2 = prompts.build_prompt("C2", "question", retrieved)
    sys_c5, user_c5 = prompts.build_prompt("C5", "question", retrieved)
    # C5 shares its system prompt with C3 and labels the documents as untrusted
    assert sys_c5 == prompts.SYSTEM_PROMPTS["C3"]
    assert "untrusted" in user_c5.lower()
    assert "untrusted" not in user_c2.lower()
