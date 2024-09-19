import pydantic


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


class AnnounceConnection(BaseMessage):
    name: str
    service: str
    pid: int
    hostname: str
    connected: bool


class RequestState(BaseMessage): ...


class UpdateState(BaseMessage):
    name: str
    service: str
    pid: int
    hostname: str
    subscribed_to: list[str]


core_topics = {
    "&_announce_connection": AnnounceConnection,
    "&_request_state": RequestState,
    "&_update_state": UpdateState,
}
