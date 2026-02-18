"""
Cost Service — Single source of truth for cost calculations.

Reads pricing from cost_config.json and provides estimate functions
used by both the /estimate endpoint (real-time preview) and job
creation (recording actual cost).
"""
import json
from pathlib import Path


class CostService:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent / "cost_config.json"
        with open(config_path, "r") as f:
            self.config = json.load(f)

    # ------------------------------------------------------------------
    # Individual cost components
    # ------------------------------------------------------------------

    def calculate_voice_cost(self, script_length: int) -> float:
        """Cost for ElevenLabs TTS based on character count."""
        return round(script_length * self.config["elevenlabs"]["cost_per_character"], 5)

    def calculate_video_cost(self, duration: int, model: str) -> float:
        """Cost for AI video generation based on duration and model."""
        models = self.config["kie_ai"]["models"]
        model_cfg = models.get(model, models["default"])
        return round(duration * model_cfg["cost_per_second"], 5)

    def calculate_music_cost(self) -> float:
        return self.config["music"]["cost_per_video"]

    def calculate_processing_cost(self) -> float:
        return self.config["processing"]["cost_per_video"]

    def is_silent_model(self, model: str) -> bool:
        """Silent models produce video without audio and need ElevenLabs."""
        return model in self.config["kie_ai"].get("silent_models", [])

    # ------------------------------------------------------------------
    # Full estimate
    # ------------------------------------------------------------------

    def estimate_total_cost(
        self,
        script_text: str = "",
        duration: int = 15,
        model: str = "seedance-1.5-pro",
    ) -> dict:
        """
        Returns a full cost breakdown dict.

        Voice cost is only included for silent models (e.g. Kling) that
        need post-generation ElevenLabs voiceover.  Models like Seedance
        and Veo already include audio so voice cost = 0.
        """
        cost_video = self.calculate_video_cost(duration, model)

        # Only charge for voice on silent models
        if self.is_silent_model(model):
            cost_voice = self.calculate_voice_cost(len(script_text))
        else:
            cost_voice = 0.0

        cost_music = self.calculate_music_cost()
        cost_processing = self.calculate_processing_cost()
        total_cost = round(cost_video + cost_voice + cost_music + cost_processing, 5)

        return {
            "cost_video": cost_video,
            "cost_voice": cost_voice,
            "cost_music": cost_music,
            "cost_processing": cost_processing,
            "total_cost": total_cost,
        }


# Singleton — import this in main.py
cost_service = CostService()
