"""Chi-square (Pairs-of-Values) steganalysis for StegoChat V1."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy import stats

from analysis.image_utils import require_rgb_image, to_rgb_array

CHANNEL_NAMES: tuple[str, str, str] = ("R", "G", "B")
PAIR_COUNT = 128  # 256 intensities grouped into (2i, 2i+1) pairs
DEFAULT_SUSPICION_THRESHOLD = 0.5
P_VALUE_DISPLAY_THRESHOLD = 1e-6


@dataclass(frozen=True)
class ChiSquareChannelResult:
    """Chi-square Pairs-of-Values result for a single RGB channel."""

    channel: str
    chi_square_statistic: float
    degrees_of_freedom: int
    p_value: float

    def likely_contains_hidden_data(
        self, threshold: float = DEFAULT_SUSPICION_THRESHOLD
    ) -> bool:
        """Return True when the p-value exceeds ``threshold``.

        A high p-value means the observed Pairs-of-Values distribution is
        suspiciously close to what LSB embedding would produce (values
        within each pair are nearly equal in frequency).
        """
        return self.p_value > threshold


@dataclass(frozen=True)
class ChiSquareReport:
    """Chi-square Pairs-of-Values results for all three RGB channels."""

    red: ChiSquareChannelResult
    green: ChiSquareChannelResult
    blue: ChiSquareChannelResult

    def for_channel(self, name: str) -> ChiSquareChannelResult:
        """Return the chi-square result for channel ``"R"``, ``"G"``, or ``"B"``."""
        if name == "R":
            return self.red
        if name == "G":
            return self.green
        if name == "B":
            return self.blue
        raise ValueError(f"unknown RGB channel name: {name!r}")

    def suspected_channel_count(
        self, threshold: float = DEFAULT_SUSPICION_THRESHOLD
    ) -> int:
        """Return how many of the three channels look embedded at ``threshold``."""
        return sum(
            1
            for name in CHANNEL_NAMES
            if self.for_channel(name).likely_contains_hidden_data(threshold)
        )


def compute_chi_square_test(image: Image.Image) -> ChiSquareReport:
    """Run the Pairs-of-Values chi-square steganalysis test on an RGB image.

    Unlike histogram/bit-plane comparison, this test does not require the
    original cover image — it is designed to flag a *suspected* stego image
    on its own, which is what makes it a genuine steganalysis technique
    rather than a before/after comparison.
    """
    require_rgb_image(image, "image")
    array = to_rgb_array(image)
    return ChiSquareReport(
        red=_channel_chi_square(array, 0, "R"),
        green=_channel_chi_square(array, 1, "G"),
        blue=_channel_chi_square(array, 2, "B"),
    )


def chi_square_report_to_rows(
    report: ChiSquareReport,
) -> list[dict[str, float | str | int | bool]]:
    """Flatten a chi-square report into rows usable by an XLSX sheet or DataFrame."""
    return [
        {
            "channel": name,
            "chi_square_statistic": round(result.chi_square_statistic, 4),
            "degrees_of_freedom": result.degrees_of_freedom,
            "p_value": result.p_value,
            "likely_contains_hidden_data": result.likely_contains_hidden_data(),
        }
        for name in CHANNEL_NAMES
        for result in [report.for_channel(name)]
    ]


def format_p_value_for_display(p_value: float) -> str:
    """Format a p-value for a human-readable table without implying zero."""
    if p_value < P_VALUE_DISPLAY_THRESHOLD:
        return "< 0,000001"
    return f"{p_value:.6g}".replace(".", ",")


def _channel_chi_square(
    array: np.ndarray, channel: int, name: str
) -> ChiSquareChannelResult:
    counts = np.bincount(array[:, :, channel].ravel(), minlength=256)[:256].astype(
        np.float64
    )

    chi_square_sum = 0.0
    degrees_of_freedom = 0
    for pair_index in range(PAIR_COUNT):
        even_count = counts[2 * pair_index]
        odd_count = counts[2 * pair_index + 1]
        expected = (even_count + odd_count) / 2.0
        if expected == 0:
            continue
        chi_square_sum += ((even_count - expected) ** 2) / expected
        degrees_of_freedom += 1

    degrees_of_freedom = max(degrees_of_freedom - 1, 1)
    p_value = float(stats.chi2.sf(chi_square_sum, degrees_of_freedom))

    return ChiSquareChannelResult(
        channel=name,
        chi_square_statistic=float(chi_square_sum),
        degrees_of_freedom=degrees_of_freedom,
        p_value=p_value,
    )
