import json
import time

from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file


def main():
    load_env_file()

    print("Loading Synthetic Data Generator Skill...")
    skill_bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
    SyntheticGeneratorSkill = skill_bundle["module"].SyntheticGeneratorSkill

    generator = SyntheticGeneratorSkill()

    dataset = []

    # We will generate 1 batch of 10 samples
    print("\nGenerating 10 samples using Gemini...")
    start_time = time.time()

    prompt = (
        "Ensure personas are extremely erratic. Use rare edge-case medical "
        "scenarios like obscure comorbidities fighting with dual-insurance."
    )

    result = generator.execute(
        {
            "domain": "medical_coding_disputes",
            "num_samples": 10,
            "entropy_temperature": 0.9,
            "diversity_prompt": prompt,
            "model_provider": "gemini",
            "model_name": "gemini-3.5-flash-lite",
        }
    )

    elapsed = time.time() - start_time
    print(f"Time Taken: {elapsed:.2f} seconds")

    if result.get("status") == "success":
        score = result.get("entropy_score")
        samples = result.get("samples", [])
        print(f"✅ Success! Entropy Score: {score}")
        print(f"Extracted {len(samples)} samples out of requested 10.")
        dataset.extend(samples)
    else:
        print(f"❌ Failed: {result.get('message')}")

    # Save the dataset
    out_file = "synthetic_dataset.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for d in dataset:
            f.write(json.dumps(d) + "\n")

    print(f"\nSaved {len(dataset)} high-entropy samples to {out_file}")


if __name__ == "__main__":
    main()
