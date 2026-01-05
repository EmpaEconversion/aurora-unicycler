"""Additional protocol validation functions used by exporters in _formats."""

from aurora_unicycler._core import BaseProtocol, Loop, Step, Tag


def tag_to_indices(protocol: BaseProtocol) -> None:
    """Convert tag steps into indices to be processed later."""
    # In a protocol the steps are 1-indexed and tags should be ignored
    # The loop function should point to the index of the step AFTER the corresponding tag
    indices = [0] * len(protocol.method)
    tags = {}
    methods_to_remove = []
    j = 0
    for i, step in enumerate(protocol.method):
        if isinstance(step, Tag):
            indices[i] = j + 1
            tags[step.tag] = j + 1
            # drop this step from the list
            methods_to_remove.append(i)
        elif isinstance(step, Step):
            j += 1
            indices[i] = j
            if isinstance(step, Loop):
                if isinstance(step.loop_to, str):
                    # If the start step is a string, it should be a tag, go to the tag index
                    try:
                        step.loop_to = tags[step.loop_to]
                    except KeyError as e:
                        msg = (
                            f"Loop step with tag {step.loop_to} "
                            "does not have a corresponding tag step."
                        )
                        raise ValueError(msg) from e
                else:
                    # If the start step is an int, it should be the NEW index of the step
                    step.loop_to = indices[step.loop_to - 1]
        else:
            methods_to_remove.append(i)
    # Remove tags and other invalid steps
    protocol.method = [step for i, step in enumerate(protocol.method) if i not in methods_to_remove]


def check_for_intersecting_loops(protocol: BaseProtocol) -> None:
    """Check if a method has intersecting loops. Cannot contain Tags."""
    loops = []
    for i, step in enumerate(protocol.method):
        if isinstance(step, Loop):
            loops.append((int(step.loop_to), i + 1))
    loops.sort()

    for i in range(len(loops)):
        for j in range(i + 1, len(loops)):
            i_start, i_end = loops[i]
            j_start, j_end = loops[j]

            # If loop j starts after loop i ends, stop checking i
            if j_start > i_end:
                break

            # Otherwise check if they intersect, completely nested is okay
            if (i_start < j_start and i_end < j_end) or (i_start > j_start and i_end > j_end):
                msg = "Protocol has intersecting loops."
                raise ValueError(msg)


def validate_capacity_c_rates(protocol: BaseProtocol) -> None:
    """Ensure if using C-rate steps, a capacity is set."""
    if not protocol.sample.capacity_mAh and any(
        getattr(s, "rate_C", None) or getattr(s, "until_rate_C", None) for s in protocol.method
    ):
        msg = "Sample capacity must be set if using C-rate steps."
        raise ValueError(msg)
