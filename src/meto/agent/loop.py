from openai import OpenAI

from meto.conf import settings

client = OpenAI(api_key=settings.LITELLM_API_KEY, base_url=settings.LITELLM_BASE_URL)


def run_agent_loop(prompt: str) -> None:
    resp = client.chat.completions.create(
        model=settings.DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    print(resp.choices[0].message.content)
