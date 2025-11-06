import pydantic


MAX_REPR_LEN = 50


class BaseMessage(pydantic.BaseModel):
    model_config = dict(extra="forbid")

    def serialize(self) -> str:
        """Serialize the data into a JSON string.

        Returns:
            The model data as a JSON string.
        """
        return self.model_dump_json()

    @classmethod
    def deserialize(cls, data: str):
        """Instantiate a model from JSON data.

        Args:
            data: A JSON string.

        Returns:
            An instantiation of the model using the JSON data.
        """
        return cls.model_validate_json(data)

    @staticmethod
    def _shorten(data):
        if isinstance(data, str):
            if len(data) <= MAX_REPR_LEN:
                return repr(data)
            else:
                return f"'{data[:MAX_REPR_LEN]}...'"
        elif isinstance(data, list):
            return f"[{', '.join([BaseMessage._shorten(el) for el in data])}]"
        elif isinstance(data, tuple):
            return f"({', '.join([BaseMessage._shorten(el) for el in data])})"
        elif isinstance(data, dict):
            return f"{{{', '.join([f'{BaseMessage._shorten(key)}: {BaseMessage._shorten(val)}' for key, val in data.items()])}}}"
        else:
            return repr(data)

    def __repr__(self):
        return f"{self.__class__.__name__}({str(self)})"

    def __str__(self):
        return ", ".join(
            [f"{prop}={self._shorten(data)}" for prop, data in self.__dict__.items()]
        )
