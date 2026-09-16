import asyncio
import json

from app.core.config import get_settings
from app.db.models.image_generation_job import ImageGenerationJob
from app.services.image_generation_service import launch_image_generation_job
from app.services.tools.base import Tool, ToolContext

settings = get_settings()

_POLL_INTERVAL_SECONDS = 2
# Local diffusion on CPU-only hardware (no GPU) is slow but does complete, unlike video —
# generous enough to cover that case without leaving a chat turn hanging indefinitely. Matches
# QuickCreatePanel's own 5-minute image timeout (frontend/src/components/QuickCreatePanel.tsx)
# — measured at ~270s for a 512x512/20-step image on a 7GB-RAM CPU-only dev machine, so 240s
# was cutting it close enough to report a false "timed out" moments before the job actually
# completed.
_MAX_WAIT_SECONDS = 300


class GenerateImageTool(Tool):
    """Runs the same job-based pipeline as the /image-generation endpoint (imagegen/scripts/
    generate.py as a separate OS process), but waits synchronously for it to finish so the
    result can be woven into this one tool-call turn — the chat protocol only supports a
    single request/response round trip per tool, not a background job the user polls."""

    name = "generate_image"
    description = (
        'Generates an image from a text description using the local image model. Args: '
        '{"prompt": "a red fox curled up in a snowy forest, watercolor style"}. Takes up to a '
        "few minutes. Only use this when the user explicitly asks you to create, draw, "
        "generate, or make an image, picture, illustration, artwork, or logo — never for "
        "photos of real, identifiable people."
    )

    async def run(self, args: dict, context: ToolContext | None = None) -> str:
        prompt = (args.get("prompt") or "").strip()
        if not prompt:
            return json.dumps({"message": "Error: no image description was given."})
        if context is None:
            return json.dumps({"message": "Error: image generation is unavailable in this context."})

        job = ImageGenerationJob(
            user_id=context.user_id,
            prompt=prompt,
            width=settings.image_gen_default_width,
            height=settings.image_gen_default_height,
            steps=settings.image_gen_default_steps,
        )
        context.db.add(job)
        context.db.commit()
        context.db.refresh(job)

        try:
            proc = launch_image_generation_job(
                str(job.id),
                str(context.user_id),
                prompt,
                None,
                job.width,
                job.height,
                job.steps,
                None,
            )
            job.pid = getattr(proc, "pid", None)
            context.db.commit()
        except OSError as exc:
            job.status = "FAILED"
            job.error_message = f"Could not launch image generation process: {exc}"
            context.db.commit()
            return json.dumps({"message": f"Error: could not start image generation ({exc})."})

        elapsed = 0
        while elapsed < _MAX_WAIT_SECONDS:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            elapsed += _POLL_INTERVAL_SECONDS
            context.db.refresh(job)
            if job.status == "COMPLETED" and job.image_id:
                return json.dumps(
                    {
                        "message": "Image generated successfully — it's shown to the user below this message.",
                        "image_id": str(job.image_id),
                    }
                )
            if job.status in ("FAILED", "CANCELLED"):
                detail = job.error_message or "no further details available."
                return json.dumps({"message": f"Error: image generation {job.status.lower()} — {detail}"})

        return json.dumps({"message": "Error: image generation is taking too long and timed out."})
