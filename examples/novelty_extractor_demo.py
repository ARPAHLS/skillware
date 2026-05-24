"""
Novelty Extractor Demo

Demonstrates how to use the data_engineering/novelty_extractor skill to
distill a large text corpus into high-signal content across multiple turns.
"""

from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file


def main():
    load_env_file()

    print("Loading Novelty Extractor skill...")
    bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
    NoveltyExtractor = bundle["module"].NoveltyExtractor

    skill = NoveltyExtractor()

    corpus_batch_1 = (
        "Bitcoin is a decentralized digital currency.\n\n"
        "Bitcoin operates without a central bank.\n\n"
        "The sky is blue and the weather is nice today.\n\n"
        "Python is a high-level programming language.\n\n"
        "Bitcoin was created by Satoshi Nakamoto."
    )

    print("\n--- Batch 1 ---")
    result1 = skill.execute(
        {
            "dataset_chunk": corpus_batch_1,
            "novelty_threshold": 0.85,
        }
    )

    if "error" in result1:
        print(f"Failed: {result1['error']}")
        return

    print("Distilled content:")
    print(result1["distilled_content"])
    print(f"Compression ratio: {result1['compression_ratio']}")
    print(f"Redundant chunks dropped: {result1['redundant_chunks_dropped']}")

    corpus_batch_2 = (
        "Bitcoin runs on a peer-to-peer network.\n\n"
        "The sky appears blue due to Rayleigh scattering.\n\n"
        "Machine learning is a subset of artificial intelligence.\n\n"
        "Bitcoin transactions are recorded on the blockchain."
    )

    print("\n--- Batch 2 (with baseline from Batch 1) ---")
    result2 = skill.execute(
        {
            "dataset_chunk": corpus_batch_2,
            "novelty_threshold": 0.85,
            "baseline_chunks": result1["distilled_content"],
        }
    )

    if "error" in result2:
        print(f"Failed: {result2['error']}")
        return

    print("Distilled content:")
    print(result2["distilled_content"])
    print(f"Compression ratio: {result2['compression_ratio']}")
    print(f"Redundant chunks dropped: {result2['redundant_chunks_dropped']}")

    full_distilled = (
        result1["distilled_content"] + "\n\n" + result2["distilled_content"]
    )
    print("\n--- Full distilled dataset ---")
    print(full_distilled)


if __name__ == "__main__":
    main()
