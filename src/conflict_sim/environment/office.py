"""Physical state: places, who is where, what a place allows. The engine knows place ids only."""

from collections.abc import Iterable

from ..models import OfficeConfig, PlaceKind, PlaceSpec

EAT_PLACES: frozenset[PlaceKind] = frozenset({"pantry", "cafeteria"})


class Office:
    def __init__(self, config: OfficeConfig, agents: Iterable[str]):
        self.places: dict[str, PlaceSpec] = {place.id: place for place in config.places}
        # The lobby is the way in and out: everyone arrives there and leaves through it.
        self.lobby = next((p.id for p in config.places if p.kind == "lobby"), config.places[0].id)
        self.location: dict[str, str] = dict.fromkeys(agents, self.lobby)

    def leave(self) -> None:
        """End of the working day: everyone goes out through the lobby, where tomorrow starts."""
        for name in self.location:
            self.location[name] = self.lobby

    def kind(self, name: str) -> PlaceKind:
        return self.places[self.location[name]].kind

    def occupants(self, place_id: str) -> list[str]:
        return [name for name, place in self.location.items() if place == place_id]

    def present(self, name: str) -> tuple[str, ...]:
        """Everyone else in my place; co-presence is what makes talk and observation possible."""
        return tuple(other for other in self.occupants(self.location[name]) if other != name)

    def free(self, place_id: str) -> int | None:
        capacity = self.places[place_id].capacity
        return None if capacity is None else capacity - len(self.occupants(place_id))

    def resources(self) -> dict[str, int]:
        """Free seats per capped place; the scarce rooms are the only resources in A."""
        return {
            place_id: free for place_id in self.places if (free := self.free(place_id)) is not None
        }
