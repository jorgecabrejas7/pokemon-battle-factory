"""
Training Controller - Controller for RL training.

This module provides the TrainingController class optimized for
RL training with step-based interfaces.

Usage:
    controller = TrainingController()
    controller.connect()
    controller.initialize_to_draft()
    
    # Run training episode
    controller.step_draft(drafter_agent)
    while not controller.is_run_complete:
        result = controller.step_battle(tactician_agent)
        if controller.phase == GamePhase.SWAP_SCREEN:
            controller.step_swap(drafter_agent)
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Tuple, List, Any, Protocol
import numpy as np

from ..core.enums import GamePhase, BattleOutcome, BattleAction, SwapAction
from ..core.exceptions import InvalidStateError
from ..config import config

from .base import BaseController, RunStats, BattleStats
from .input import InputController, Button
from .game_executor import GameExecutor

logger = logging.getLogger(__name__)


# =============================================================================
# Result Dataclasses
# =============================================================================

@dataclass
class PhaseResult:
    """Result of executing a game phase."""
    success: bool
    phase: str
    next_phase: GamePhase
    data: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TurnResult:
    """Result of executing a single battle turn."""
    success: bool
    action: int
    reward: float
    battle_ended: bool
    outcome: Optional[BattleOutcome] = None
    data: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class EpisodeResult:
    """Result of a complete Battle Factory episode."""
    success: bool
    win_streak: int
    battles_won: int
    battles_lost: int
    total_turns: int
    duration_seconds: float
    phases_completed: List[str] = field(default_factory=list)
    error: Optional[str] = None


# =============================================================================
# Agent Protocols
# =============================================================================

class DrafterAgent(Protocol):
    """Protocol for drafter agents."""
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray: ...


class TacticianAgent(Protocol):
    """Protocol for tactician agents."""
    def __call__(
        self, 
        obs: np.ndarray, 
        phase: GamePhase, 
        mask: np.ndarray
    ) -> int: ...


# =============================================================================
# Training Controller
# =============================================================================

class TrainingController(BaseController):
    """
    Controller optimized for RL training.
    
    Provides step-based interfaces for:
    - Phase-level stepping (draft, battle, swap)
    - Turn-level stepping (individual battle turns)
    - Full episode execution
    
    Designed for integration with RLlib and similar frameworks.
    """
    
    def __init__(
        self,
        backend=None,
        verbose: bool = False,
        auto_wait: bool = True,
    ):
        """
        Initialize training controller.
        
        Args:
            backend: EmeraldBackend instance
            verbose: Enable verbose logging
            auto_wait: Automatically wait after actions
        """
        super().__init__(backend, verbose)
        self.auto_wait = auto_wait
        
        # GameExecutor is initialized after connect() when input controller is available
        self.executor: Optional[GameExecutor] = None
    
    def _ensure_executor(self) -> None:
        """Ensure GameExecutor is initialized (after connect)."""
        if self.executor is None and self.input is not None:
            self.executor = GameExecutor(
                input_ctrl=self.input,
                backend=self.backend,
                verbose=self.verbose
            )
    
    # =========================================================================
    # Initialization / Navigation
    # =========================================================================
    
    def initialize_to_draft(self, from_title: bool = True) -> bool:
        """
        Navigate from current position to draft screen.
        
        Args:
            from_title: Whether starting from title screen
            
        Returns:
            True if successfully reached draft screen
        """
        self._ensure_executor()
        logger.info("[TrainingController] Delegate initialization to GameExecutor...")
        return self.executor.initialize_to_draft(from_title=from_title)
    
    # =========================================================================
    # Phase-Level Steps
    # =========================================================================
    
    def step_draft(self, agent: Optional[DrafterAgent] = None) -> PhaseResult:
        """
        Execute draft phase - select 3 Pokemon from 6 rentals.
        
        Args:
            agent: Drafter agent. If None, uses random selection.
            
        Returns:
            PhaseResult with outcome
        """
        logger.info("=== DRAFT PHASE ===")
        
        if self.phase != GamePhase.DRAFT_SCREEN:
            return PhaseResult(
                success=False,
                phase="draft",
                next_phase=self.phase,
                error=f"Not in draft phase (current: {self.phase.name})"
            )
        
        try:
            # Get observation
            obs = self.get_draft_observation()
            
            # Get agent action or random
            if agent:
                selections = agent(obs, self.phase)
            else:
                selections = np.random.choice(6, size=3, replace=False)
            
            logger.info(f"  Selecting Pokemon: {list(selections)}")
            
            # Execute draft selections
            self._execute_draft(selections)
            
            # Transition to next phase
            self.transition_to(GamePhase.BATTLE_READY, force=True)
            
            return PhaseResult(
                success=True,
                phase="draft",
                next_phase=self.phase,
                data={"selections": list(selections)}
            )
            
        except Exception as e:
            logger.error(f"Draft failed: {e}")
            return PhaseResult(
                success=False,
                phase="draft",
                next_phase=GamePhase.ERROR,
                error=str(e)
            )
    
    def _execute_draft(self, selections: np.ndarray) -> None:
        """Execute draft selection inputs using GameExecutor."""
        self._ensure_executor()
        self.executor.set_up_draft_phase()
        self.executor.execute_draft_selection(list(int(s) for s in selections))
    
    def step_battle(self, agent: Optional[TacticianAgent] = None) -> PhaseResult:
        """
        Execute an entire battle (multiple turns).
        
        Args:
            agent: Tactician agent. If None, uses random actions.
            
        Returns:
            PhaseResult with battle outcome
        """
        logger.info("=== BATTLE PHASE ===")
        
        # Wait for battle to start if needed
        if self.phase == GamePhase.BATTLE_READY:
            if not self.wait_for_battle_start():
                return PhaseResult(
                    success=False,
                    phase="battle",
                    next_phase=self.phase,
                    error="Timeout waiting for battle start"
                )
        
        if not self.phase.is_battle_phase:
            return PhaseResult(
                success=False,
                phase="battle",
                next_phase=self.phase,
                error=f"Not in battle phase (current: {self.phase.name})"
            )
        
        try:
            self.reset_battle()
            
            # Battle loop
            while True:
                # Wait for input
                if not self.wait_for_input():
                    break
                
                # Get observation and mask
                obs = self.get_battle_observation()
                mask = self.get_action_mask()
                
                # Get action
                if agent:
                    action = agent(obs, self.phase, mask)
                else:
                    valid = np.where(mask > 0)[0]
                    action = int(np.random.choice(valid)) if len(valid) > 0 else 0
                
                # Execute turn
                result = self.step_turn(action)
                
                if result.battle_ended:
                    break
            
            # Handle outcome
            outcome = self._get_battle_outcome()
            
            if outcome == BattleOutcome.WIN:
                self.run_stats.battles_won += 1
                self.run_stats.win_streak += 1
                self.run_stats.current_battle += 1
                
                if self.run_stats.win_streak >= config.game.max_streak:
                    self.transition_to(GamePhase.RUN_COMPLETE, force=True)
                elif self.run_stats.current_battle >= config.game.battles_per_round:
                    self.run_stats.current_battle = 0
                    self.transition_to(GamePhase.SWAP_SCREEN, force=True)
                else:
                    self.transition_to(GamePhase.BATTLE_READY, force=True)
            else:
                self.run_stats.battles_lost += 1
                self.transition_to(GamePhase.RUN_COMPLETE, force=True)
            
            logger.info(f"  Battle ended: {outcome.name}, streak={self.run_stats.win_streak}")
            
            return PhaseResult(
                success=True,
                phase="battle",
                next_phase=self.phase,
                data={
                    "outcome": outcome.name,
                    "turns": self.battle_stats.turn_count,
                    "total_reward": self.battle_stats.total_reward,
                }
            )
            
        except Exception as e:
            logger.error(f"Battle failed: {e}")
            import traceback
            traceback.print_exc()
            return PhaseResult(
                success=False,
                phase="battle",
                next_phase=GamePhase.ERROR,
                error=str(e)
            )
    
    def step_turn(self, action: int) -> TurnResult:
        """
        Execute a single battle turn.
        
        Args:
            action: Action to take (0-3=Move, 4-5=Switch)
            
        Returns:
            TurnResult with outcome
        """
        if self.phase != GamePhase.IN_BATTLE:
            return TurnResult(
                success=False,
                action=action,
                reward=0.0,
                battle_ended=False,
                error=f"Not waiting for input (phase: {self.phase.name})"
            )
        
        try:
            # Record pre-action state
            pre_state = self.refresh_battle_state()
            pre_enemy_hp = pre_state.enemy_active_pokemon.hp_percentage if pre_state.enemy_active_pokemon else 0
            pre_player_hp = pre_state.active_pokemon.current_hp if pre_state.active_pokemon else 0
            
            # Execute action using GameExecutor
            self._ensure_executor()
            self.executor.execute_battle_action(action)
            
            self.battle_stats.turn_count += 1
            self.run_stats.total_turns += 1
            
            # Wait for result
            self.wait_for_input()
            
            # Read post-action state
            post_state = self.refresh_battle_state()
            post_enemy_hp = post_state.enemy_active_pokemon.hp_percentage if post_state.enemy_active_pokemon else 0
            post_player_hp = post_state.active_pokemon.current_hp if post_state.active_pokemon else 0
            
            # Calculate reward
            outcome = self._get_battle_outcome()
            reward = self.calculate_battle_reward(
                pre_enemy_hp, post_enemy_hp,
                pre_player_hp, post_player_hp,
                outcome
            )
            
            self.battle_stats.total_reward += reward
            battle_ended = outcome != BattleOutcome.ONGOING
            
            return TurnResult(
                success=True,
                action=action,
                reward=reward,
                battle_ended=battle_ended,
                outcome=outcome if battle_ended else None,
                data={
                    "turn": self.battle_stats.turn_count,
                    "damage_dealt": pre_enemy_hp - post_enemy_hp,
                    "damage_taken": pre_player_hp - post_player_hp,
                }
            )
            
        except Exception as e:
            logger.error(f"Turn failed: {e}")
            return TurnResult(
                success=False,
                action=action,
                reward=0.0,
                battle_ended=False,
                error=str(e)
            )
    
    # NOTE: _execute_move and _execute_switch have been moved to GameExecutor.
    # Use self.executor.execute_battle_action(action) instead.
    
    def step_swap(self, agent: Optional[DrafterAgent] = None) -> PhaseResult:
        """
        Execute swap phase - decide whether to swap Pokemon.
        
        Args:
            agent: Drafter agent. If None, random decision.
            
        Returns:
            PhaseResult with outcome
        """
        logger.info("=== SWAP PHASE ===")
        
        if self.phase != GamePhase.SWAP_SCREEN:
            return PhaseResult(
                success=False,
                phase="swap",
                next_phase=self.phase,
                error=f"Not in swap phase (current: {self.phase.name})"
            )
        
        try:
            # Get observation
            obs = self.get_swap_observation()
            
            # Get action
            if agent:
                action_arr = agent(obs, self.phase)
                action = int(action_arr[0]) if len(action_arr) > 0 else 0
            else:
                # 30% chance to swap
                action = int(np.random.choice([0, 1, 2, 3], p=[0.7, 0.1, 0.1, 0.1]))
            
            logger.info(f"  Swap decision: {action} (0=keep)")
            
            # Execute swap using GameExecutor
            self._ensure_executor()
            self.executor.set_up_swap_phase()
            self.executor.execute_swap_decision(action)
            if action > 0:
                self.run_stats.swaps_made += 1
            
            self.transition_to(GamePhase.BATTLE_READY, force=True)
            
            return PhaseResult(
                success=True,
                phase="swap",
                next_phase=self.phase,
                data={"action": action, "swapped": action > 0}
            )
            
        except Exception as e:
            logger.error(f"Swap failed: {e}")
            return PhaseResult(
                success=False,
                phase="swap",
                next_phase=GamePhase.ERROR,
                error=str(e)
            )
    
    # =========================================================================
    # Full Episode
    # =========================================================================
    
    def run_episode(
        self,
        drafter: Optional[DrafterAgent] = None,
        tactician: Optional[TacticianAgent] = None,
    ) -> EpisodeResult:
        """
        Run a complete Battle Factory episode.
        
        Args:
            drafter: Agent for draft/swap decisions
            tactician: Agent for battle decisions
            
        Returns:
            EpisodeResult with statistics
        """
        logger.info("\n" + "=" * 60)
        logger.info("STARTING EPISODE")
        logger.info("=" * 60)
        
        start_time = time.time()
        phases = []
        
        try:
            self.reset_run()
            
            # Draft
            result = self.step_draft(drafter)
            phases.append("draft")
            if not result.success:
                raise Exception(f"Draft failed: {result.error}")
            
            # Battle loop
            battle_num = 0
            while not self.is_run_complete:
                battle_num += 1
                
                # Battle
                result = self.step_battle(tactician)
                phases.append(f"battle_{battle_num}")
                
                if not result.success:
                    raise Exception(f"Battle failed: {result.error}")
                
                # Swap if needed
                if self.phase == GamePhase.SWAP_SCREEN:
                    result = self.step_swap(drafter)
                    phases.append("swap")
                    if not result.success:
                        raise Exception(f"Swap failed: {result.error}")
            
            duration = time.time() - start_time
            
            logger.info(f"\n{'=' * 60}")
            logger.info(f"EPISODE COMPLETE - Streak: {self.run_stats.win_streak}")
            logger.info(f"{'=' * 60}")
            
            return EpisodeResult(
                success=True,
                win_streak=self.run_stats.win_streak,
                battles_won=self.run_stats.battles_won,
                battles_lost=self.run_stats.battles_lost,
                total_turns=self.run_stats.total_turns,
                duration_seconds=duration,
                phases_completed=phases,
            )
            
        except Exception as e:
            logger.error(f"Episode failed: {e}")
            import traceback
            traceback.print_exc()
            
            return EpisodeResult(
                success=False,
                win_streak=self.run_stats.win_streak,
                battles_won=self.run_stats.battles_won,
                battles_lost=self.run_stats.battles_lost,
                total_turns=self.run_stats.total_turns,
                duration_seconds=time.time() - start_time,
                phases_completed=phases,
                error=str(e),
            )

