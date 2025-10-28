"""E2B Vision Tool - Full parity with SandboxVisionTool"""

import base64
import mimetypes
import os
from io import BytesIO
from typing import Optional
from pydantic import Field, PrivateAttr

from PIL import Image

from app.e2b.tool_base import E2BToolsBase
from app.tool.base import ToolResult
from app.utils.files_utils import clean_path
from app.utils.logger import logger


# Maximum file sizes
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_COMPRESSED_SIZE = 5 * 1024 * 1024

# Compression settings
DEFAULT_MAX_WIDTH = 1920
DEFAULT_MAX_HEIGHT = 1080
DEFAULT_JPEG_QUALITY = 85
DEFAULT_PNG_COMPRESS_LEVEL = 6

_VISION_DESCRIPTION = """
A sandbox-based vision tool that allows the agent to read image files inside the sandbox using the see_image action.
* Only the see_image action is supported, with the parameter being the relative path of the image under /home/user.
* The image will be compressed and converted to base64 for use in subsequent context.
* Supported formats: JPG, PNG, GIF, WEBP. Maximum size: 10MB.
"""


class E2BVisionTool(E2BToolsBase):
    """Tool for viewing images in E2B sandbox"""

    name: str = "e2b_vision"
    description: str = _VISION_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["see_image"],
                "description": "Vision action to perform, currently only supports see_image",
            },
            "file_path": {
                "type": "string",
                "description": "Relative path of image under /home/user, e.g. 'screenshots/image.png'",
            },
        },
        "required": ["action", "file_path"],
        "dependencies": {"see_image": ["file_path"]},
    }

    workspace_path: str = Field(default="/home/user", exclude=True)

    def clean_path(self, path: str) -> str:
        """Clean and normalize a path"""
        return clean_path(path, self.workspace_path)

    def compress_image(self, image_bytes: bytes, mime_type: str, file_path: str):
        """Compress image while maintaining reasonable quality"""
        try:
            img = Image.open(BytesIO(image_bytes))

            # Convert to RGB if needed
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(
                    img, mask=img.split()[-1] if img.mode == "RGBA" else None
                )
                img = background

            # Resize if too large
            width, height = img.size
            if width > DEFAULT_MAX_WIDTH or height > DEFAULT_MAX_HEIGHT:
                ratio = min(DEFAULT_MAX_WIDTH / width, DEFAULT_MAX_HEIGHT / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Compress based on format
            output = BytesIO()
            if mime_type == "image/gif":
                img.save(output, format="GIF", optimize=True)
                output_mime = "image/gif"
            elif mime_type == "image/png":
                img.save(
                    output,
                    format="PNG",
                    optimize=True,
                    compress_level=DEFAULT_PNG_COMPRESS_LEVEL,
                )
                output_mime = "image/png"
            else:
                img.save(
                    output, format="JPEG", quality=DEFAULT_JPEG_QUALITY, optimize=True
                )
                output_mime = "image/jpeg"

            compressed_bytes = output.getvalue()
            return compressed_bytes, output_mime

        except Exception:
            return image_bytes, mime_type

    async def execute(
        self, action: str, file_path: Optional[str] = None, **kwargs
    ) -> ToolResult:
        """
        Execute vision action, currently only supports see_image.
        Args:
            action: Must be 'see_image'
            file_path: Relative path to image file
        """
        if action != "see_image":
            return self.fail_response(f"Unknown vision action: {action}")

        if not file_path:
            return self.fail_response("file_path parameter cannot be empty")

        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            cleaned_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{cleaned_path}"

            # Check if file exists and get size
            check_result = self.sandbox.exec(f"test -f {full_path} && stat -c%s {full_path} || echo 'not_exists'")
            if "not_exists" in check_result.stdout:
                return self.fail_response(f"Image file not found: '{cleaned_path}'")

            try:
                file_size = int(check_result.stdout.strip())
            except:
                file_size = 0

            if file_size > MAX_IMAGE_SIZE:
                return self.fail_response(
                    f"Image file '{cleaned_path}' is too large ({file_size / (1024*1024):.2f}MB), "
                    f"maximum allowed {MAX_IMAGE_SIZE / (1024*1024)}MB."
                )

            # Read image file as binary
            try:
                image_bytes = self.sandbox.filesystem_read(full_path, binary=True)
                if image_bytes is None:
                    return self.fail_response(f"Cannot read image file: {cleaned_path}")
            except Exception as e:
                return self.fail_response(f"Cannot read image file: {cleaned_path} - {e}")

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(full_path)
            if not mime_type or not mime_type.startswith("image/"):
                ext = os.path.splitext(cleaned_path)[1].lower()
                if ext in [".jpg", ".jpeg"]:
                    mime_type = "image/jpeg"
                elif ext == ".png":
                    mime_type = "image/png"
                elif ext == ".gif":
                    mime_type = "image/gif"
                elif ext == ".webp":
                    mime_type = "image/webp"
                else:
                    return self.fail_response(
                        f"Unsupported or unknown image format: '{cleaned_path}'. Supported: JPG, PNG, GIF, WEBP."
                    )

            # Compress image
            compressed_bytes, compressed_mime_type = self.compress_image(
                image_bytes, mime_type, cleaned_path
            )

            if len(compressed_bytes) > MAX_COMPRESSED_SIZE:
                return self.fail_response(
                    f"Image file '{cleaned_path}' is still too large after compression "
                    f"({len(compressed_bytes) / (1024*1024):.2f}MB), "
                    f"maximum allowed {MAX_COMPRESSED_SIZE / (1024*1024)}MB."
                )

            # Convert to base64
            base64_image = base64.b64encode(compressed_bytes).decode("utf-8")

            logger.info(f"Successfully loaded and compressed image '{cleaned_path}' "
                       f"(from {file_size / 1024:.1f}KB to {len(compressed_bytes) / 1024:.1f}KB)")

            return ToolResult(
                output=f"Successfully loaded and compressed image '{cleaned_path}'",
                base64_image=base64_image,
            )

        except Exception as e:
            logger.error(f"Error in see_image execution: {e}")
            return self.fail_response(f"see_image execution error: {str(e)}")
