"""
Custom Exception Hierarchy for Battle Factory RL System.

Provides structured error handling with specific exception types
for different error scenarios, improving debugging and error recovery.

Usage:
    from src.core.exceptions import ConnectionError, MemoryReadError
    
    try:
        backend.connect()
    except ConnectionError as e:
        logger.error(f"Failed to connect: {e}")
"""

from __future__ import annotations

from typing import Optional, Any


class BattleFactoryError(Exception):
    """
    Base exception for all Battle Factory errors.
    
    All custom exceptions inherit from this, allowing code to catch
    all Battle Factory-related errors with a single except clause.
    """
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


# =============================================================================
# Connection Errors
# =============================================================================

class ConnectionError(BattleFactoryError):
    """
    Raised when connection to emulator fails.
    
    This can occur when:
    - mGBA is not running
    - connector.lua is not loaded
    - Game is paused (script doesn't run)
    - Network issues
    """
    
    def __init__(
        self, 
        message: str = "Failed to connect to emulator",
        host: Optional[str] = None,
        port: Optional[int] = None,
        reason: Optional[str] = None,
    ):
        details = {}
        if host:
            details["host"] = host
        if port:
            details["port"] = port
        if reason:
            details["reason"] = reason
        super().__init__(message, details)
        self.host = host
        self.port = port
        self.reason = reason


class DisconnectedError(BattleFactoryError):
    """Raised when operation attempted on disconnected backend."""
    
    def __init__(self, message: str = "Not connected to emulator"):
        super().__init__(message)


class CommandTimeoutError(BattleFactoryError):
    """Raised when a command to the emulator times out."""
    
    def __init__(
        self,
        command: str,
        timeout: float,
        message: Optional[str] = None,
    ):
        msg = message or f"Command timed out after {timeout}s"
        super().__init__(msg, {"command": command, "timeout": timeout})
        self.command = command
        self.timeout = timeout


# =============================================================================
# Memory Errors
# =============================================================================

class MemoryError(BattleFactoryError):
    """Base class for memory-related errors."""
    pass


class MemoryReadError(MemoryError):
    """
    Raised when reading from emulator memory fails.
    
    Common causes:
    - Invalid memory address
    - Read during state transition
    - Corrupted data
    """
    
    def __init__(
        self,
        address: int,
        size: int = 0,
        message: Optional[str] = None,
    ):
        msg = message or f"Failed to read memory at 0x{address:08X}"
        super().__init__(msg, {"address": hex(address), "size": size})
        self.address = address
        self.size = size


class MemoryWriteError(MemoryError):
    """Raised when writing to emulator memory fails."""
    
    def __init__(
        self,
        address: int,
        value: Any,
        message: Optional[str] = None,
    ):
        msg = message or f"Failed to write to memory at 0x{address:08X}"
        super().__init__(msg, {"address": hex(address), "value": value})
        self.address = address
        self.value = value


class DecryptionError(MemoryError):
    """Raised when Pokemon data decryption fails."""
    
    def __init__(
        self,
        message: str = "Failed to decrypt Pokemon data",
        checksum_expected: Optional[int] = None,
        checksum_actual: Optional[int] = None,
    ):
        details = {}
        if checksum_expected is not None:
            details["expected"] = hex(checksum_expected)
        if checksum_actual is not None:
            details["actual"] = hex(checksum_actual)
        super().__init__(message, details)


# =============================================================================
# State Errors
# =============================================================================

class StateError(BattleFactoryError):
    """Base class for game state errors."""
    pass


class InvalidStateError(StateError):
    """
    Raised when an operation is attempted in wrong game state.
    
    Example: Trying to execute battle action when in draft phase.
    """
    
    def __init__(
        self,
        current_state: str,
        expected_states: list[str],
        operation: str,
        message: Optional[str] = None,
    ):
        msg = message or f"Cannot {operation} in state {current_state}"
        super().__init__(msg, {
            "current": current_state,
            "expected": expected_states,
            "operation": operation,
        })
        self.current_state = current_state
        self.expected_states = expected_states
        self.operation = operation


class StateTransitionError(StateError):
    """Raised when state transition fails."""
    
    def __init__(
        self,
        from_state: str,
        to_state: str,
        message: Optional[str] = None,
    ):
        msg = message or f"Failed to transition from {from_state} to {to_state}"
        super().__init__(msg, {"from": from_state, "to": to_state})
        self.from_state = from_state
        self.to_state = to_state


class PhaseTimeoutError(StateError):
    """Raised when waiting for a game phase times out."""
    
    def __init__(
        self,
        phase: str,
        timeout: float,
        message: Optional[str] = None,
    ):
        msg = message or f"Timeout waiting for {phase} phase"
        super().__init__(msg, {"phase": phase, "timeout": timeout})
        self.phase = phase
        self.timeout = timeout


# =============================================================================
# Action Errors
# =============================================================================

class ActionError(BattleFactoryError):
    """Base class for action-related errors."""
    pass


class InvalidActionError(ActionError):
    """Raised when an invalid action is attempted."""
    
    def __init__(
        self,
        action: int,
        valid_actions: list[int],
        message: Optional[str] = None,
    ):
        msg = message or f"Invalid action {action}"
        super().__init__(msg, {
            "action": action,
            "valid": valid_actions,
        })
        self.action = action
        self.valid_actions = valid_actions


class ActionMaskedError(ActionError):
    """Raised when attempting a masked (invalid) action."""
    
    def __init__(
        self,
        action: int,
        mask: list[float],
        message: Optional[str] = None,
    ):
        msg = message or f"Action {action} is masked (not available)"
        super().__init__(msg, {"action": action, "mask": mask})
        self.action = action
        self.mask = mask


# =============================================================================
# Data Errors
# =============================================================================

class DataError(BattleFactoryError):
    """Base class for data-related errors."""
    pass


class KnowledgeBaseError(DataError):
    """Raised when knowledge base query fails."""
    
    def __init__(
        self,
        query: str,
        message: Optional[str] = None,
    ):
        msg = message or f"Knowledge base query failed"
        super().__init__(msg, {"query": query})
        self.query = query


class EntityNotFoundError(DataError):
    """Raised when a game entity (species, move, etc.) is not found."""
    
    def __init__(
        self,
        entity_type: str,
        entity_id: int,
        message: Optional[str] = None,
    ):
        msg = message or f"{entity_type} with ID {entity_id} not found"
        super().__init__(msg, {"type": entity_type, "id": entity_id})
        self.entity_type = entity_type
        self.entity_id = entity_id


# =============================================================================
# Navigation Errors
# =============================================================================

class NavigationError(BattleFactoryError):
    """Base class for navigation errors."""
    pass


class NavigationTimeoutError(NavigationError):
    """Raised when navigation sequence times out."""
    
    def __init__(
        self,
        step: str,
        timeout: float,
        message: Optional[str] = None,
    ):
        msg = message or f"Navigation timed out at step: {step}"
        super().__init__(msg, {"step": step, "timeout": timeout})
        self.step = step
        self.timeout = timeout


class UnexpectedScreenError(NavigationError):
    """Raised when game is on unexpected screen during navigation."""
    
    def __init__(
        self,
        expected_screen: str,
        actual_indicators: Optional[dict] = None,
        message: Optional[str] = None,
    ):
        msg = message or f"Expected screen: {expected_screen}"
        super().__init__(msg, {
            "expected": expected_screen,
            "indicators": actual_indicators or {},
        })
        self.expected_screen = expected_screen
        self.actual_indicators = actual_indicators


# =============================================================================
# Agent Errors  
# =============================================================================

class AgentError(BattleFactoryError):
    """Base class for agent-related errors."""
    pass


class AgentNotReadyError(AgentError):
    """Raised when agent is used before initialization."""
    
    def __init__(
        self,
        agent_type: str,
        message: Optional[str] = None,
    ):
        msg = message or f"{agent_type} agent not initialized"
        super().__init__(msg, {"agent_type": agent_type})
        self.agent_type = agent_type

