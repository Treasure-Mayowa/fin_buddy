# FinBuddy

## Problem
Financial literacy remains critically low in Nigeria and across Africa, with millions lacking access to quality financial advice. Traditional financial advisory services are:

- Expensive: High consultation fees exclude low-income populations
- Inaccessible: Limited physical presence in rural and underserved areas
- Complex: Technical jargon creates barriers for everyday users
- Not Localized: Generic advice doesn't address individual financial contexts and challenges

The result? Poor financial decisions, lack of investment knowledge, and perpetual financial insecurity for millions of Africans.

## Solution

![FinBuddy Demo](assets/FinBuddy-Demo.gif)

FinBuddy is an AI-powered WhatsApp bot that democratizes financial advice by providing:

🎯 Instant Financial Guidance
- 24/7 availability through WhatsApp (Nigeria's most popular messaging platform)
- Real-time responses to financial questions and concerns
- No app downloads or complex registrations required

🧠 Intelligent AI Advisory

- Fine-tuned GPT-OSS 20B model optimized for Nigerian financial contexts
- Multi-layered fallback system: Local AI → API 
- RAG (Retrieval-Augmented Generation) for contextually relevant advice

advice

🏦 Comprehensive Financial Coverage

- Investment strategies and portfolio management
- Debt management and credit improvement
- Insurance and risk assessment
- Retirement and tax planning
- Nigerian-specific financial regulations and opportunities

🎯 Localized & Accessible

- Trained on Nigerian financial data and regulations
- Understands local banks, investment platforms, and financial products
- Simple conversational interface in English
- Free basic advice with premium consultation booking (in progress)

## Tech Stack
- Framework: Fast API
- Tools: Redis, Prometheus, Grafana
- Machine Learning: Transformer, Pandas, PyTorch, Unsloth

## Model Fine-Tuning
For a detailed outline on the model fine-tuning process, you can read the [training README](./training/README.md)

