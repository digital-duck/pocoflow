# PocoFlow Structured Output v2

Resume parser that extracts structured YAML data from free-text resumes using LLM prompting with validation.

## Usage

```bash
python main.py --provider anthropic
python main.py --provider ollama --model llama3.2
python main.py --resume path/to/resume.txt --provider openrouter
```

## How it works

1. Sends resume text + target skill list to the LLM
2. LLM returns structured YAML with name, email, experience, and skill indexes
3. Validates the parsed YAML structure (retries up to 3 times on failure)
4. Displays the structured data and matched skills
