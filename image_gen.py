import logging

logger = logging.getLogger(__name__)


class ImageGenerator:
	"""Disabled: image generation is not used. Kept for compatibility."""
	def __init__(self, *args, **kwargs):
		self.disabled = True
		self.client = None

	def generate_image_bytes(self, *args, **kwargs):
		return None


