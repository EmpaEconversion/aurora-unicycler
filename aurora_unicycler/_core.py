"""Core unicycler classes for protocol attributes and different experimental steps."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

from aurora_unicycler.version import __version__


def _coerce_c_rate(v: float | str | None) -> float | None:
    """Allow C rates to be defined as fraction strings.

    e.g. "1/5" -> 0.2, "C/3" -> 0.333333, "D/2" -> -0.5.
    """
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        return float(v)
    except ValueError:
        # If it's a string, check if it looks like a fraction
        if isinstance(v, str):
            v = v.replace(" ", "")
            parts = v.split("/")
            if len(parts) == 2:
                # count Cs and Ds in string
                if parts[0].count("C") + parts[0].count("D") > 1:
                    msg = f"Invalid C-rate format: {v}"
                    raise ValueError(msg)  # noqa: B904
                if "C" in parts[0]:
                    parts[0] = parts[0].replace("C", "").strip()
                    nom = 1.0 if parts[0] == "" else float(parts[0])
                elif "D" in parts[0]:
                    parts[0] = parts[0].replace("D", "").strip()
                    nom = -float(parts[0]) if parts[0] else -1.0
                else:
                    nom = float(parts[0])
                denom = float(parts[1])
                return nom / denom
    msg = f"Invalid rate_C value: {v}"
    raise ValueError(msg)


def _empty_string_is_none(v: float | str | None) -> float | None:
    """Empty strings are interpretted as None type."""
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    return float(v)


class UnicyclerParams(BaseModel):
    """Unicycler details - generated automatically.

    Attributes:
        version: aurora-unicycler version used to generate protocol, set
            automatically.

    """

    version: str = Field(default=__version__)
    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="after")
    def _update_version(self) -> Self:
        """Update version when model is read in or created."""
        if self.version != __version__:
            return self.model_copy(update={"version": __version__})
        return self


class SampleParams(BaseModel):
    """Sample parameters.

    Attributes:
        name: Sample name.
        capacity_mAh: Sample capacity in mAh, used to calculate current from C-rates.

    """

    name: str = Field(default="$NAME")
    capacity_mAh: float | None = Field(gt=0, default=None)

    model_config = ConfigDict(extra="forbid")


class RecordParams(BaseModel):
    """Recording parameters.

    Attributes:
        current_mA: Current change in mA which triggers recording data.
        voltage_V: Voltage change in V which triggers recording data.
        time_s: Time in seconds between recording data.

    """

    current_mA: float | None = None
    voltage_V: float | None = None
    time_s: float = Field(gt=0)

    model_config = ConfigDict(extra="forbid")


class SafetyParams(BaseModel):
    """Safety parameters, i.e. limits before cancelling the entire experiment.

    Attributes:
        max_voltage_V: Maximum voltage in V.
        min_voltage_V: Minimum voltage in V.
        max_current_mA: Maximum current in mA.
        min_current_mA: Minimum current in mA (can be negative).
        delay_s: How long in seconds limits must be exceeded before cancelling.

    """

    max_voltage_V: float | None = None
    min_voltage_V: float | None = None
    max_current_mA: float | None = None
    min_current_mA: float | None = None
    max_capacity_mAh: float | None = Field(ge=0, default=None)
    delay_s: float | None = Field(ge=0, default=None)

    model_config = ConfigDict(extra="forbid")


class Step(BaseModel):
    """Base class for all steps."""

    # optional id field
    id: str | None = Field(default=None, description="Optional ID for the technique step")
    model_config = ConfigDict(extra="forbid")


class OpenCircuitVoltage(Step):
    """Open circuit voltage step.

    Attributes:
        until_time_s: Duration of step in seconds.

    """

    step: Literal["open_circuit_voltage"] = Field(default="open_circuit_voltage", frozen=True)
    until_time_s: float = Field(gt=0)

    @field_validator("until_time_s", mode="before")
    @classmethod
    def _allow_empty_string(cls, v: float | str) -> float | None:
        """Empty string is interpreted as None."""
        return _empty_string_is_none(v)


class ConstantCurrent(Step):
    """Constant current step.

    At least one of `rate_C` or `current_mA` must be set. If `rate_C` is used, a
    sample capacity must be set in the Protocol, and it will take priority over
    `current_mA`.

    The termination ('until') conditions are OR conditions, the step will end
    when any one of these is met.

    Attributes:
        rate_C: (optional) The current applied in C-rate units (i.e. mA per mAh).
        current_mA: (optional) The current applied in mA.
        until_time_s: Duration of step in seconds.
        until_voltage_V: End step when this voltage in V is reached.

    """

    step: Literal["constant_current"] = Field(default="constant_current", frozen=True)
    rate_C: float | None = None
    current_mA: float | None = None
    until_time_s: float | None = None
    until_voltage_V: float | None = None

    @field_validator("rate_C", mode="before")
    @classmethod
    def _parse_c_rate(cls, v: float | str) -> float | None:
        """C-rate can be a string e.g. "C/2"."""
        return _coerce_c_rate(v)

    @field_validator("current_mA", "until_time_s", "until_voltage_V", mode="before")
    @classmethod
    def _allow_empty_string(cls, v: float | str) -> float | None:
        """Empty string is interpreted as None."""
        return _empty_string_is_none(v)

    @model_validator(mode="after")
    def _ensure_rate_or_current(self) -> Self:
        """Ensure at least one of rate_C or current_mA is set."""
        has_rate_C = self.rate_C is not None and self.rate_C != 0
        has_current_mA = self.current_mA is not None and self.current_mA != 0
        if not (has_rate_C or has_current_mA):
            msg = "Either rate_C or current_mA must be set and non-zero."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _ensure_stop_condition(self) -> Self:
        """Ensure at least one stop condition is set."""
        has_time_s = self.until_time_s is not None and self.until_time_s != 0
        has_voltage_V = self.until_voltage_V is not None and self.until_voltage_V != 0
        if not (has_time_s or has_voltage_V):
            msg = "Either until_time_s or until_voltage_V must be set and non-zero."
            raise ValueError(msg)
        return self


class ConstantVoltage(Step):
    """Constant voltage step.

    The termination ('until') conditions are OR conditions, the step will end
    when any one of these is met. If both `until_rate_C` and `until_current_mA`
    are set, C-rate will take priority.

    Note that in most cyclers, a voltage is not applied directly, instead the
    current is adjusted to achieve a certain voltage.

    Attributes:
        voltage_V: The voltage applied in V.
        until_time_s: Duration of step in seconds.
        until_rate_C: End step when this C-rate (i.e. mA per mAh) is reached.
        until_current_mA: End step when this current in mA is reached.

    """

    step: Literal["constant_voltage"] = Field(default="constant_voltage", frozen=True)
    voltage_V: float
    until_time_s: float | None = None
    until_rate_C: float | None = None
    until_current_mA: float | None = None

    @field_validator("until_rate_C", mode="before")
    @classmethod
    def _parse_c_rate(cls, v: float | str) -> float | None:
        """C-rate can be a string e.g. "C/2"."""
        return _coerce_c_rate(v)

    @field_validator("voltage_V", "until_time_s", "until_current_mA", mode="before")
    @classmethod
    def _allow_empty_string(cls, v: float | str) -> float | None:
        """Empty string is interpreted as None."""
        return _empty_string_is_none(v)

    @model_validator(mode="after")
    def _check_stop_condition(self) -> Self:
        """Ensure at least one of until_rate_C or until_current_mA is set."""
        has_time_s = self.until_time_s is not None and self.until_time_s != 0
        has_rate_C = self.until_rate_C is not None and self.until_rate_C != 0
        has_current_mA = self.until_current_mA is not None and self.until_current_mA != 0
        if not (has_time_s or has_rate_C or has_current_mA):
            msg = "Either until_time_s, until_rate_C, or until_current_mA must be set and non-zero."
            raise ValueError(msg)
        return self


class ImpedanceSpectroscopy(Step):
    """Electrochemical Impedance Spectroscopy (EIS) step.

    Only one of `amplitude_V` (PEIS) or `amplitude_mA` (GEIS) can be set.

    Attributes:
        amplitude_V: (optional) Oscillation amplitude in V.
        amplitude_mA: (optional) Oscillation amplitude in mA.
        start_frequency_Hz: Beginning frequency in Hz.
        end_frequency_Hz: End frequency in Hz.
        points_per_decade: How many points to measure per decade, i.e. power of 10.
        measures_per_point: How many measurements to average per point.
        drift_correction: Corrects for drift in the system - requires twice as
            many measurements. Compensates measured current/voltage at frequency
            `f_m` with points`f_m-1` and `f_m+1` using the formula for PEIS
            `∆I(f_m) = I(f_m) + (I(f_m+1) - I(f_m-1))/2`, (and similar for V in
            GEIS). Operates on both real and imaginary parts.

    """

    step: Literal["impedance_spectroscopy"] = Field(default="impedance_spectroscopy", frozen=True)
    amplitude_V: float | None = None
    amplitude_mA: float | None = None
    start_frequency_Hz: float = Field(ge=1e-5, le=1e5, description="Start frequency in Hz")
    end_frequency_Hz: float = Field(ge=1e-5, le=1e5, description="End frequency in Hz")
    points_per_decade: int = Field(gt=0, default=10)
    measures_per_point: int = Field(gt=0, default=1)
    drift_correction: bool | None = Field(default=False, description="Apply drift correction")
    model_config = ConfigDict(extra="forbid")

    @field_validator("amplitude_V", "amplitude_mA", mode="before")
    @classmethod
    def _allow_empty_string(cls, v: float | str) -> float | None:
        """Empty string is interpreted as None."""
        return _empty_string_is_none(v)

    @model_validator(mode="after")
    def _validate_amplitude(self) -> Self:
        """Cannot set both amplitude_V and amplitude_mA."""
        if self.amplitude_V is not None and self.amplitude_mA is not None:
            msg = "Cannot set both amplitude_V and amplitude_mA."
            raise ValueError(msg)
        if self.amplitude_V is None and self.amplitude_mA is None:
            msg = "Either amplitude_V or amplitude_mA must be set."
            raise ValueError(msg)
        return self


class Loop(Step):
    """Loop step.

    Supports both looping to a tag or the step number (1-indexed). It is
    recommened to use tags to avoid potential errors with indexing or when
    adding/removing steps.

    Internally, tags are converted to indexes with the correct indexing when
    sending to cyclers.

    Attributes:
        loop_to: The tag or step number (1-indexed) to loop back to.
        cycle_count: How many times to loop. This is the TOTAL number of cycles.
            Different cyclers define this differently. Here, a cycle_count of 3
            means 3 cycles in total will be performed.

    """

    step: Literal["loop"] = Field(default="loop", frozen=True)
    loop_to: Annotated[int | str, Field()] = Field(default=1)
    cycle_count: int = Field(gt=0)
    model_config = ConfigDict(extra="forbid")

    @field_validator("loop_to")
    @classmethod
    def _validate_loop_to(cls, v: int | str) -> int | str:
        """Ensure loop_to is a positive integer or a string."""
        if isinstance(v, int) and v <= 0:
            msg = "Start step must be positive integer or a string"
            raise ValueError(msg)
        if isinstance(v, str) and v.strip() == "":
            msg = "Start step cannot be empty"
            raise ValueError(msg)
        return v


class Tag(Step):
    """Tag step.

    Used in combination with the Loop step, e.g.
    ```
    [
        Tag(tag="formation")
        # Your cycling steps here
        Loop(loop_to="formation", cycle_count=3)
    ]
    ```

    This will loop over the cycling steps 3 times. Put the tag before the step
    you want to loop to.

    Can also be used for comments or organisation, but note that it will only be
    stored in unicycler, when sending to e.g. Biologic or Neware, loops/tags are
    converted to indices and the tag steps are removed.

    Attributes:
        tag: The tag name.

    """

    step: Literal["tag"] = Field(default="tag", frozen=True)
    tag: str = Field(default="")

    model_config = ConfigDict(extra="forbid")


AnyTechnique = Annotated[
    OpenCircuitVoltage | ConstantCurrent | ConstantVoltage | ImpedanceSpectroscopy | Loop | Tag,
    Field(discriminator="step"),
]


class BaseProtocol(BaseModel):
    """Internal base protocol model. Users should use `Protocol` instead.

    This class provides attributes used to define a Unicycler protocol and constructors.
    It does not contain methods to convert to different formats.
    """

    unicycler: UnicyclerParams = Field(default_factory=UnicyclerParams)
    sample: SampleParams = Field(default_factory=SampleParams)
    record: RecordParams
    safety: SafetyParams = Field(default_factory=SafetyParams)
    method: Sequence[AnyTechnique] = Field(min_length=1)  # Ensure at least one step

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _check_no_blank_steps(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Check if any 'blank' steps are in the method before trying to parse them."""
        steps = values.get("method", [])
        for i, step in enumerate(steps):
            if (isinstance(step, Step) and not hasattr(step, "step")) or (
                isinstance(step, dict) and ("step" not in step or not step["step"])
            ):
                msg = f"Step at index {i} is incomplete, needs a 'step' type."
                raise ValueError(msg)
        return values

    @model_validator(mode="after")
    def _validate_loops_and_tags(self) -> Self:
        """Ensure that if a loop uses a string, it is a valid tag."""
        loop_tags = {
            i: step.loop_to
            for i, step in enumerate(self.method)
            if isinstance(step, Loop) and isinstance(step.loop_to, str)
        }
        loop_idx = {
            i: step.loop_to
            for i, step in enumerate(self.method)
            if isinstance(step, Loop) and isinstance(step.loop_to, int)
        }
        tags = {i: step.tag for i, step in enumerate(self.method) if isinstance(step, Tag)}

        # Cannot have duplicate tags
        tag_list = list(tags.values())
        if len(tag_list) != len(set(tag_list)):
            duplicate_tags = {"'" + tag + "'" for tag in tag_list if tag_list.count(tag) > 1}
            msg = "Duplicate tags: " + ", ".join(duplicate_tags)
            raise ValueError(msg)

        tags_rev = {v: k for k, v in tags.items()}  # to map from tag to index

        # indexed loops cannot go on itself or forwards
        for i, loop_start in loop_idx.items():
            if loop_start >= i:
                msg = f"Loop start index {loop_start} cannot be on or after the loop index {i}."
                raise ValueError(msg)

        # Loops cannot go forwards to tags, or back one index to a tag
        for i, loop_tag in loop_tags.items():
            if loop_tag not in tags_rev:
                msg = f"Tag '{loop_tag}' is missing."
                raise ValueError(msg)
            # loop_tag is in tags, ensure i is larger than the tag index
            tag_i = tags_rev[loop_tag]
            if i <= tag_i:
                msg = f"Loops must go backwards, '{loop_tag}' goes forwards ({i}->{tag_i})."
                raise ValueError(msg)
            if i == tag_i + 1:
                msg = f"Loop '{loop_tag}' cannot start immediately after its tag."
                raise ValueError(msg)
        return self

    @classmethod
    def from_dict(
        cls,
        data: dict,
        sample_name: str | None = None,
        sample_capacity_mAh: float | None = None,
    ) -> Self:
        """Create a Protocol from a dictionary."""
        # If values given then overwrite
        data.setdefault("sample", {})
        if sample_name:
            data["sample"]["name"] = sample_name
        if sample_capacity_mAh:
            data["sample"]["capacity_mAh"] = sample_capacity_mAh
        return cls(**data)

    @classmethod
    def from_json(
        cls,
        json_file: str | Path,
        sample_name: str | None = None,
        sample_capacity_mAh: float | None = None,
    ) -> Self:
        """Create a Protocol from a JSON file."""
        json_file = Path(json_file)
        with json_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, sample_name, sample_capacity_mAh)

    def to_dict(self) -> dict:
        """Convert a Protocol to a dictionary."""
        return self.model_dump()

    def to_json(self, json_file: str | Path | None = None, indent: int = 4) -> str:
        """Dump model as JSON string, optionally save as a JSON file."""
        json_string = self.model_dump_json(indent=indent)
        if json_file:
            json_file = Path(json_file)
            json_file.parent.mkdir(parents=True, exist_ok=True)
            with json_file.open("w", encoding="utf-8") as f:
                f.write(json_string)
        return json_string
