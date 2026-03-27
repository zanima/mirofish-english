#!/usr/bin/env python3
"""
Translate Chinese text in MiroFish source files to English.
Strategy: extract only lines containing Chinese, translate those, replace in file.
This is ~10-50x faster than regenerating entire files.
"""

import os
import re
import json
import shutil
from openai import OpenAI

ZH = re.compile(r'[\u4e00-\u9fff]')
BASE = os.path.expanduser("~/MiroFish")

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "kimi-k2.5:cloud"

SYSTEM_PROMPT = (
    "You are a code translator. You will receive a JSON array of source code lines that contain Chinese text. "
    "Translate ONLY the Chinese characters in each line to natural English. "
    "Rules:\n"
    "- Preserve ALL code syntax exactly: quotes, brackets, commas, HTML tags, Vue directives, CSS classes, "
    "variable names, function names, API paths\n"
    "- Only replace the Chinese characters/words with their English meaning\n"
    "- Return a JSON array of the same length with translated lines, nothing else\n"
    "- Example in:  ['// 获取用户列表', '  label: \"提交\",']\n"
    "- Example out: ['// Get user list', '  label: \"Submit\",']\n"
    "Return ONLY the JSON array, no explanation, no markdown fences."
)

FILES = [
    # Frontend
    "frontend/src/App.vue",
    "frontend/src/components/GraphPanel.vue",
    "frontend/src/components/Step2EnvSetup.vue",
    "frontend/src/components/Step5Interaction.vue",
    "frontend/src/components/HistoryDatabase.vue",
    "frontend/src/components/Step3Simulation.vue",
    "frontend/src/components/Step4Report.vue",
    "frontend/src/components/Step1GraphBuild.vue",
    "frontend/src/api/graph.js",
    "frontend/src/api/simulation.js",
    "frontend/src/api/index.js",
    "frontend/src/api/report.js",
    "frontend/src/views/Home.vue",
    "frontend/src/views/InteractionView.vue",
    "frontend/src/views/SimulationView.vue",
    "frontend/src/views/ReportView.vue",
    "frontend/src/views/MainView.vue",
    "frontend/src/views/Process.vue",
    "frontend/src/views/SimulationRunView.vue",
    "frontend/src/store/pendingUpload.js",
    # Backend
    "backend/run.py",
    "backend/app/config.py",
    "backend/app/__init__.py",
    "backend/app/utils/file_parser.py",
    "backend/app/utils/__init__.py",
    "backend/app/utils/logger.py",
    "backend/app/utils/zep_paging.py",
    "backend/app/utils/retry.py",
    "backend/app/utils/llm_client.py",
    "backend/app/models/task.py",
    "backend/app/models/__init__.py",
    "backend/app/models/project.py",
    "backend/app/api/simulation.py",
    "backend/app/api/graph.py",
    "backend/app/api/__init__.py",
    "backend/app/api/report.py",
    "backend/app/services/report_agent.py",
    "backend/app/services/simulation_runner.py",
    "backend/app/services/zep_tools.py",
    "backend/app/services/text_processor.py",
    "backend/app/services/__init__.py",
    "backend/app/services/oasis_profile_generator.py",
    "backend/app/services/simulation_manager.py",
    "backend/app/services/ontology_generator.py",
    "backend/app/services/simulation_ipc.py",
    "backend/app/services/zep_entity_reader.py",
    "backend/app/services/graph_builder.py",
    "backend/app/services/zep_graph_memory_updater.py",
    "backend/app/services/simulation_config_generator.py",
]

BATCH_SIZE = 30  # lines per LLM call


def translate_lines(lines: list[str]) -> list[str]:
    """Send a batch of Chinese-containing lines to the model, get English back."""
    payload = json.dumps(lines, ensure_ascii=False)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ],
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
        raw = raw[: raw.rfind("```")] if raw.rstrip().endswith("```") else raw
    try:
        result = json.loads(raw)
        if isinstance(result, list) and len(result) == len(lines):
            return result
    except Exception:
        pass
    # Fallback: return original if parse fails
    print(f"\n    [WARN] parse failed, keeping originals for this batch")
    return lines


def translate_file(rel_path: str) -> None:
    full_path = os.path.join(BASE, rel_path)
    if not os.path.exists(full_path):
        print(f"  SKIP (not found): {rel_path}")
        return

    with open(full_path, encoding="utf-8") as f:
        all_lines = f.readlines()

    zh_indices = [i for i, ln in enumerate(all_lines) if ZH.search(ln)]
    if not zh_indices:
        print(f"  SKIP (no Chinese): {rel_path}")
        return

    print(f"  {rel_path}  ({len(zh_indices)} lines to translate)", flush=True)

    # Backup once
    bak = full_path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(full_path, bak)

    translated_lines = list(all_lines)

    # Process in batches
    for batch_start in range(0, len(zh_indices), BATCH_SIZE):
        batch_idx = zh_indices[batch_start: batch_start + BATCH_SIZE]
        batch_lines = [all_lines[i].rstrip("\n") for i in batch_idx]
        print(f"    batch {batch_start//BATCH_SIZE + 1}/{-(-len(zh_indices)//BATCH_SIZE)}"
              f" ({len(batch_lines)} lines)...", end=" ", flush=True)
        translated = translate_lines(batch_lines)
        for i, new_line in zip(batch_idx, translated):
            # Preserve original line ending
            ending = "\n" if all_lines[i].endswith("\n") else ""
            translated_lines[i] = new_line + ending
        print("done")

    with open(full_path, "w", encoding="utf-8") as f:
        f.writelines(translated_lines)


def main():
    print(f"MiroFish → English  |  model: {MODEL}  |  batch: {BATCH_SIZE} lines\n")
    for rel in FILES:
        translate_file(rel)
    print("\nAll done.")


if __name__ == "__main__":
    main()
