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
        product_type: str = "digital",
        num_scenes: int = 2
    ) -> dict:
        """
        Returns a full cost breakdown dict.

        Voice cost is only included for silent models (e.g. Kling) that
        need post-generation ElevenLabs voiceover. Models like Seedance
        and Veo already include audio so voice cost = 0.
        """
        cost_video = 0.0
        cost_image = 0.0

        if product_type == "physical":
            # Physical flow: 2-step generation per scene (Nano Banana Image + Veo Video)
            # 1. Image Generation Cost
            cost_per_image = self.config["kie_ai"]["models"].get("nano_banana_pro", {}).get("cost_per_image", 0.10)
            cost_image = num_scenes * cost_per_image
            
            # 2. Video Animation Cost (Veo 3.1 Fast)
            video_model_config = self.config["kie_ai"]["models"].get("veo-3.1-fast", {})
            cost_per_second_video = video_model_config.get("cost_per_second", 0.02)
            cost_video = duration * cost_per_second_video

        else:
            # Digital flow: Single video generation call (Seedance/Kling)
            cost_video = self.calculate_video_cost(duration, model)

        # Voice cost handling
        if product_type == "physical":
             # Veo is silent, so we always need voiceover
             cost_voice = self.calculate_voice_cost(len(script_text))
        elif self.is_silent_model(model):
            cost_voice = self.calculate_voice_cost(len(script_text))
        else:
            cost_voice = 0.0

        cost_music = self.calculate_music_cost()
        cost_processing = self.calculate_processing_cost()
        total_cost = round(cost_video + cost_image + cost_voice + cost_music + cost_processing, 5)

        return {
            "cost_video": round(cost_video, 4),
            "cost_image": round(cost_image, 4),
            "cost_voice": round(cost_voice, 4),
            "cost_music": round(cost_music, 4),
            "cost_processing": round(cost_processing, 4),
            "total_cost": round(total_cost, 4),
        }


# Singleton — import this in main.py
cost_service = CostService()
