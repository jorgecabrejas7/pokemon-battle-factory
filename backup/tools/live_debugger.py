#!/usr/bin/env python3
"""
Pokemon Battle Factory - Live Debugger TUI

A Textual-based terminal UI for debugging and inspecting Pokemon Emerald
game state via the mGBA backend.

Usage:
    python tools/live_debugger.py [--backend mgba|mock]
"""
import sys
import os
import argparse
import logging
from datetime import datetime
from typing import Optional, List

# Suppress all logging to prevent TUI interference
logging.disable(logging.CRITICAL)

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.panel import Panel
    from rich.align import Align
    from rich.console import Group
    
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, VerticalScroll
    from textual.widgets import Header, Footer, Static, ListView, ListItem, Label, Button
    from textual.reactive import reactive
    from textual.binding import Binding
except ImportError:
    print("Error: textual or rich is not installed. Please run 'pip install textual rich'.")
    sys.exit(1)

from src.backends.emerald.memory_reader import (
    MemoryReader, PartyPokemon, BattleMon, RentalMon, FrontierState
)
from src.backends.emerald.constants import FACILITY_FACTORY
from src.core.knowledge import (
    get_species_name, get_move_name, get_item_name, 
    get_frontier_mon, get_species_base_stats
)
from src.core.dataclasses import BattleState, PlayerPokemon, EnemyPokemon

class DataView(Static):
    """Widget to display the data tables."""
    pass

class MenuList(ListView):
    """Sidebar menu."""
    pass

class DebuggerApp(App):
    """Textual TUI for Pokemon Debugger."""

    CSS = """
    Screen {
        layout: vertical;
    }

    Horizontal {
        height: 100%;
    }

    #sidebar {
        dock: left;
        width: 20;
        height: 100%;
        background: $panel;
        border-right: vkey $accent;
    }

    #sidebar Label {
        padding: 1 2;
        background: $boost;
        width: 100%;
        text-align: center;
        text-style: bold;
    }

    MenuList {
        height: 100%;
    }
    
    ListItem {
        padding: 1 2;
    }

    #content {
        height: 100%;
        padding: 1 2;
    }

    DataView {
        height: auto;
        min-height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh Data"),
    ]

    def __init__(self, backend, backend_name: str):
        super().__init__()
        self.backend = backend
        self.backend_name = backend_name
        self.reader = MemoryReader(backend)
        self.current_view = "rich_battle"
        self.last_refresh = datetime.now()
        self.status_message = "Ready"
        self.status_ok = True

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        
        with Horizontal():
            with Container(id="sidebar"):
                yield Label("MENU")
                yield MenuList(
                    ListItem(Label("Rich Battle State"), id="rich_battle"),
                    ListItem(Label("Player Party"), id="player_party"),
                    ListItem(Label("Enemy Party"), id="enemy_party"),
                    ListItem(Label("Battle Mons (Raw)"), id="battle_mons"),
                    ListItem(Label("Rentals"), id="rental_mons"),
                    ListItem(Label("Frontier"), id="frontier_state"),
                    ListItem(Label("Weather"), id="weather"),
                    ListItem(Label("Connection"), id="ping"),
                )
            
            with VerticalScroll(id="content"):
                yield DataView(id="data_view")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = f"Pokemon Debugger - {self.backend_name}"
        self.query_one(MenuList).index = 0
        self.refresh_data()
        
        # Auto-refresh every 2 seconds
        self.set_interval(2.0, self.refresh_data)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle menu selection."""
        if event.item and event.item.id:
            self.current_view = event.item.id
            self.refresh_data()

    def action_refresh(self) -> None:
        """Manually refresh data."""
        self.refresh_data()

    def refresh_data(self) -> None:
        """Fetch data from backend and update view."""
        self.last_refresh = datetime.now()
        view = self.query_one(DataView)
        
        try:
            renderable = self.get_renderable()
            view.update(renderable)
            self.sub_title = f"{self.status_message} | Last update: {self.last_refresh.strftime('%H:%M:%S')}"
        except Exception as e:
            view.update(Panel(f"[red]Error updating view: {e}[/]", title="Error"))
            self.status_ok = False
            self.status_message = "Error"

    def get_renderable(self):
        """Get the rich renderable for the current view."""
        try:
            if self.current_view == "rich_battle":
                state = self.backend.read_battle_state()
                self.status_message = f"Turn: {state.turn_count} | Outcome: {state.battle_outcome.name}"
                return self.render_rich_battle(state)

            elif self.current_view == "player_party":
                party = self.reader.read_player_party()
                self.status_message = f"Player: {len(party)} Pokemon"
                return self.render_party(party, "Player Party")
            
            elif self.current_view == "enemy_party":
                party = self.reader.read_enemy_party()
                self.status_message = f"Enemy: {len(party)} Pokemon"
                return self.render_party(party, "Enemy Party")
            
            elif self.current_view == "battle_mons":
                mons = self.reader.read_battle_mons()
                self.status_message = f"Battle: {len(mons)} active"
                return self.render_battle_mons(mons)
            
            elif self.current_view == "rental_mons":
                rentals = self.reader.read_rental_mons()
                self.status_message = f"Rentals: {len(rentals)}"
                return self.render_rental_mons(rentals)
            
            elif self.current_view == "frontier_state":
                state = self.reader.read_frontier_state()
                self.status_message = "Frontier state loaded"
                return self.render_frontier_state(state)
            
            elif self.current_view == "weather":
                weather = self.reader.read_battle_weather()
                self.status_message = f"Weather: {weather}"
                return self.render_weather(weather)
            
            elif self.current_view == "ping":
                ok = self.reader.ping()
                self.status_message = "PONG!" if ok else "Failed"
                return self.render_connection(ok)
            
            return Panel("Select an option from the menu", title="Welcome")

        except Exception as e:
            self.status_message = f"Error: {str(e)[:20]}"
            # Print full trace for debugging if needed, but TUI might hide it
            return Panel(f"[red]Error fetching data: {e}[/]", title="Error")

    # -------------------------------------------------------------------------
    # Renderers
    # -------------------------------------------------------------------------

    def render_rich_battle(self, state: BattleState) -> Panel:
        """Render the full rich battle state."""
        grid = Table.grid(expand=True, padding=(1, 2))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        
        # --- Player Panel ---
        p_mon = state.active_pokemon
        if p_mon:
            p_table = Table(box=box.SIMPLE, show_header=False)
            p_table.add_row("[bold]Species:[/]", get_species_name(p_mon.species_id))
            p_table.add_row("[bold]Level:[/]", str(p_mon.level))
            
            hp_color = "green"
            if p_mon.hp > 0:
                pct = p_mon.current_hp / p_mon.hp
                if pct < 0.25: hp_color = "red"
                elif pct < 0.5: hp_color = "yellow"
            
            p_table.add_row("[bold]HP:[/]", f"[{hp_color}]{p_mon.current_hp}/{p_mon.hp}[/]")
            p_table.add_row("[bold]Stats:[/]", f"A:{p_mon.attack} D:{p_mon.defense} S:{p_mon.speed} SA:{p_mon.sp_attack} SD:{p_mon.sp_defense}")
            
            move_txt = "\n".join([f"- {m.name} ({m.current_pp})" for m in p_mon.moves])
            p_table.add_row("[bold]Moves:[/]", move_txt)
            p_panel = Panel(p_table, title="Player (Active)", border_style="green")
        else:
            p_panel = Panel("No Active Pokemon", title="Player (Active)", border_style="dim")

        # --- Enemy Panel ---
        e_mon = state.enemy_active_pokemon
        if e_mon:
            e_table = Table(box=box.SIMPLE, show_header=False)
            species_name = get_species_name(e_mon.species_id)
            e_table.add_row("[bold]Species:[/]", species_name)
            e_table.add_row("[bold]Level:[/]", str(e_mon.level))
            e_table.add_row("[bold]HP %:[/]", f"{e_mon.hp_percentage:.1f}%")
            
            # Base Stats
            base = get_species_base_stats(e_mon.species_id)
            base_str = f"A:{base['base_attack']} D:{base['base_defense']} S:{base['base_speed']} SA:{base['base_sp_attack']} SD:{base['base_sp_defense']}"
            e_table.add_row("[bold]Base Stats:[/]", base_str)
            e_table.add_row("[bold]Types:[/]", f"{base['type1']}/{base['type2']}")
            
            # Revealed Moves
            if e_mon.revealed_moves:
                move_txt = "\n".join([f"- {m.name}" for m in e_mon.revealed_moves])
            else:
                move_txt = "[dim]None revealed[/]"
            e_table.add_row("[bold]Known Moves:[/]", move_txt)
            
            e_panel = Panel(e_table, title="Enemy (Active)", border_style="red")
        else:
            e_panel = Panel("No Active Pokemon", title="Enemy (Active)", border_style="dim")
            
        grid.add_row(p_panel, e_panel)
        
        # --- Info Panel ---
        info_table = Table.grid(padding=(0, 2))
        is_in_battle = self.reader.is_in_battle()
        info_table.add_row(f"[bold]In Battle:[/]", str(is_in_battle))
        info_table.add_row(f"[bold]Input Needed:[/]", str(state.is_waiting_for_input))
        info_table.add_row(f"[bold]Outcome:[/]", state.battle_outcome.name)
        info_table.add_row(f"[bold]Last Move:[/]", f"{get_move_name(state.last_move_used)} (User: {state.last_move_user})")
        
        # Use rich.console.Group to group renderables, avoiding Textual Container usage here
        return Panel(
            Group(
                Panel(info_table, title="Status", box=box.ROUNDED),
                grid
            ),
            title=f"Rich Battle State", 
            box=box.ROUNDED
        )

    def render_party(self, party: List[PartyPokemon], title: str) -> Panel:
        if not party:
            return Panel("[dim]No Pokemon found[/]", title=title, box=box.ROUNDED)
        
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 1), expand=True)
        table.add_column("#", no_wrap=True)
        table.add_column("Pokemon", no_wrap=True)
        table.add_column("Lv", no_wrap=True)
        table.add_column("HP", no_wrap=True)
        table.add_column("Stats (A/D/S/SA/SD)", no_wrap=True)
        table.add_column("Moves")
        
        for i, mon in enumerate(party, 1):
            species = get_species_name(mon.species_id)
            hp_pct = (mon.current_hp / mon.max_hp * 100) if mon.max_hp > 0 else 0
            hp_color = "green" if hp_pct > 50 else "yellow" if hp_pct > 25 else "red"
            
            stats = f"{mon.attack}/{mon.defense}/{mon.speed}/{mon.sp_attack}/{mon.sp_defense}"
            
            moves = [get_move_name(m) for m in mon.moves if m > 0]
            moves_str = ", ".join(moves)
            
            table.add_row(
                str(i),
                species,
                str(mon.level),
                f"[{hp_color}]{mon.current_hp}/{mon.max_hp}[/]",
                stats,
                moves_str
            )
        
        return Panel(table, title=title, box=box.ROUNDED)

    def render_battle_mons(self, mons: List[BattleMon]) -> Panel:
        if not mons:
            return Panel("[dim]Not in battle[/]", title="Battle", box=box.ROUNDED)
        
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 1), expand=True)
        table.add_column("Slot", no_wrap=True)
        table.add_column("Pokemon", no_wrap=True)
        table.add_column("HP", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Stat Stages")
        
        slots = ["Player", "Enemy", "Ally", "Foe2"]
        
        for i, mon in enumerate(mons):
            species = get_species_name(mon.species_id)
            hp_pct = (mon.current_hp / mon.max_hp * 100) if mon.max_hp > 0 else 0
            hp_color = "green" if hp_pct > 50 else "yellow" if hp_pct > 25 else "red"
            
            status = mon.status_name
            status_color = "green" if status == "Healthy" else "red"
            
            stages = []
            names = ["A", "D", "S", "SA", "SD", "Ac", "Ev"]
            for j, (n, s) in enumerate(zip(names, mon.stat_stages[1:])):
                if s != 0:
                    c = "green" if s > 0 else "red"
                    stages.append(f"[{c}]{n}{s:+d}[/]")
            stages_str = " ".join(stages) if stages else "[dim]---[/]"
            
            table.add_row(
                slots[i] if i < len(slots) else f"S{i}",
                species,
                f"[{hp_color}]{mon.current_hp}/{mon.max_hp}[/]",
                f"[{status_color}]{status}[/]",
                Text.from_markup(stages_str)
            )
        
        return Panel(table, title="Active Battle", box=box.ROUNDED)

    def render_rental_mons(self, rentals: List[RentalMon]) -> Panel:
        if not rentals:
            return Panel("[dim]No rentals found[/]", title="Rentals", box=box.ROUNDED)
        
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 1), expand=True)
        table.add_column("#", no_wrap=True)
        table.add_column("Pokemon", no_wrap=True)
        table.add_column("Nature", no_wrap=True)
        table.add_column("Item", no_wrap=True)
        table.add_column("Moves")
        
        for rental in rentals:
            mon = get_frontier_mon(rental.frontier_mon_id)
            if mon:
                moves = ", ".join(m for m in mon['moves'] if m != "---")
                table.add_row(
                    str(rental.slot + 1),
                    mon['species_name'],
                    mon['nature'],
                    mon['item_name'],
                    moves
                )
            else:
                table.add_row(str(rental.slot + 1), f"ID:{rental.frontier_mon_id}", "?", "?", "?")
        
        return Panel(table, title="Factory Rentals", box=box.ROUNDED)

    def render_frontier_state(self, state: Optional[FrontierState]) -> Panel:
        if not state:
            return Panel("[dim]Could not read state[/]", title="Frontier", box=box.ROUNDED)
        
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_row("[bold]Facility:[/]", state.facility_name)
        table.add_row("[bold]Mode:[/]", 'Singles' if state.battle_mode == 0 else 'Doubles')
        table.add_row("[bold]Level:[/]", 'Lv50' if state.level_mode == 0 else 'Open')
        table.add_row("[bold]Streak:[/]", f"[cyan]{state.win_streak}[/]")
        if state.facility == FACILITY_FACTORY:
            table.add_row("[bold]Rents:[/]", str(state.rental_count))
            
        return Panel(table, title="Frontier State", box=box.ROUNDED)

    def render_weather(self, weather: int) -> Panel:
        name = self.reader.get_weather_name(weather)
        color = "cyan" if name != "None" else "dim"
        return Panel(Align.center(f"[{color}]{name}[/]\n[dim](0x{weather:02X})[/]"), title="Weather", box=box.ROUNDED)

    def render_connection(self, ok: bool) -> Panel:
        if ok:
            return Panel(Align.center("[bold green]PONG - Connected![/]"), title="Connection", box=box.ROUNDED)
        return Panel(Align.center("[bold red]Failed to connect[/]"), title="Connection", box=box.ROUNDED)


def main():
    parser = argparse.ArgumentParser(description="Pokemon Live Debugger (Textual)")
    parser.add_argument("--backend", choices=["mock", "mgba"], default="mgba")
    args = parser.parse_args()
    
    # Setup backend before starting TUI
    print("Initializing backend...")
    
    backend = None
    backend_name = "Unknown"
    
    if args.backend == "mock":
        from src.backends.emerald.mock import MockEmeraldBackend
        backend = MockEmeraldBackend("")
        backend_name = "Mock"
    else:
        try:
            from src.backends.emerald.backend import EmeraldBackend
            backend = EmeraldBackend("")
            backend_name = "mGBA"
        except ImportError as e:
            print(f"Import failed: {e}")
            print("Using Mock Backend")
            from src.backends.emerald.mock import MockEmeraldBackend
            backend = MockEmeraldBackend("")
            backend_name = "Mock"
    
    try:
        backend.connect("")
        print(f"Connected to {backend_name}!")
    except Exception as e:
        print(f"Connection failed: {e}")
        if args.backend != "mock":
            print("Falling back to Mock")
            from src.backends.emerald.mock import MockEmeraldBackend
            backend = MockEmeraldBackend("")
            backend_name = "Mock"
            backend.connect("")
    
    # Run App
    app = DebuggerApp(backend, backend_name)
    app.run()

if __name__ == "__main__":
    main()
