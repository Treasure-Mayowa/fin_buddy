# Fine-Tuning GPT-OSS

In order to ensure optimal performance particularly for the Nigerian contexts, we fine-tuned the recently released GPT-OSS 20B model by OpenAI. As a reasoning model, it required a reasoning dataset to align both reasoning and output tokens for financial advisory tasks.

After evaluating existing models and datasets on Hugging Face and Kaggle, we discovered:

- Generic models lacked Nigerian financial context and local knowledge
- Existing datasets didn't cover Nigerian banking, investment platforms, or regulations
- Western-focused advice didn't translate well to African financial realities
- Currency and economic context required localization for Naira and Nigerian markets

