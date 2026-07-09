from typing import Callable, List

from filemaker_odata.operations.base import (
    BatchOperation,
    BatchOperationResponse,
    FileMakerConfig,
)
from filemaker_odata.operations.create import CreateOperation
from filemaker_odata.operations.delete import DeleteOperation
from filemaker_odata.operations.update import UpdateOperation

BatchCallback = Callable[[List[BatchOperation]], List[BatchOperationResponse]]


class OperationBuilder:
    """Collects batch operations, then runs them via ``execute()``."""

    def __init__(self, config: FileMakerConfig, callback: BatchCallback):
        self._config = config
        self._callback = callback
        self._operations: List[BatchOperation] = []

    def create(self, *, table: str, record: dict) -> "OperationBuilder":
        self._operations.append(CreateOperation(config=self._config, table=table, record=record))
        return self

    def update(self, *, table: str, record: dict) -> "OperationBuilder":
        self._operations.append(UpdateOperation(config=self._config, table=table, record=record))
        return self

    def delete(self, *, table: str, id: str) -> "OperationBuilder":
        self._operations.append(DeleteOperation(config=self._config, table=table, id=id))
        return self

    def execute(self) -> List[BatchOperationResponse]:
        return self._callback(self._operations)
