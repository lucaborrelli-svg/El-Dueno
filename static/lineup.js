document.addEventListener("DOMContentLoaded", () => {
  const squadPanel = document.querySelector(".squad-panel");
  if (!squadPanel) return;

  const status = squadPanel.querySelector(".lineup-selection-status");
  let selectedPlayer = null;

  function setSelected(button, selected) {
    button.setAttribute("aria-pressed", String(selected));
  }

  function updatePlayerCard(button, player) {
    button.dataset.playerId = player.id;
    button.dataset.playerName = player.name;
    button.dataset.position = player.position;
    button.dataset.overall = player.overall;
    button.dataset.crest = player.crest;
    button.querySelector(".lineup-player-name").textContent = player.name;
    button.querySelector(".lineup-player-details").textContent =
      button.closest(".pitch-player")
        ? `${player.position} · ${player.overall}`
        : `${player.position} · ${player.overall} OVR`;

    const isStarter = Boolean(button.closest(".pitch-player"));
    const icon = player.crest
      ? document.createElement("img")
      : document.createElement("span");
    icon.className = isStarter
      ? player.crest
        ? "pitch-player-crest"
        : "pitch-player-initial"
      : player.crest
        ? "squad-crest-icon"
        : "substitute-position";
    if (player.crest) {
      icon.src = player.crest;
      icon.alt = "";
      icon.loading = "lazy";
      icon.addEventListener("error", () => icon.remove());
    } else {
      icon.textContent = player.name.trim().charAt(0).toUpperCase();
    }
    const currentIcon = button.querySelector(
      ".pitch-player-crest, .pitch-player-initial, .squad-crest-icon, .substitute-position",
    );
    if (currentIcon) {
      button.replaceChild(icon, currentIcon);
    } else {
      button.insertBefore(icon, button.firstChild);
    }

    const lineupValue = button
      .closest(".pitch-player")
      ?.querySelector(".lineup-player-value");
    if (lineupValue) lineupValue.value = player.id;
  }

  squadPanel.addEventListener("click", (event) => {
    const button = event.target.closest(".lineup-player");
    if (!button || !squadPanel.contains(button)) return;

    if (!selectedPlayer) {
      selectedPlayer = button;
      setSelected(button, true);
      status.textContent = `${button.dataset.playerName} seleccionado. Ahora elegí a quién reemplazar.`;
      return;
    }

    if (selectedPlayer === button) {
      setSelected(button, false);
      selectedPlayer = null;
      status.textContent = "Selección cancelada. Elegí dos jugadores para hacer un cambio.";
      return;
    }

    const playerData = (playerButton) => ({
      id: playerButton.dataset.playerId,
      name: playerButton.dataset.playerName,
      position: playerButton.dataset.position,
      overall: playerButton.dataset.overall,
      crest: playerButton.dataset.crest,
    });
    const firstPlayer = playerData(selectedPlayer);
    const secondPlayer = playerData(button);
    updatePlayerCard(selectedPlayer, secondPlayer);
    updatePlayerCard(button, firstPlayer);
    setSelected(selectedPlayer, false);
    setSelected(button, false);
    selectedPlayer = null;
    status.textContent = "Cambio realizado. Guardá la alineación para conservarlo.";
  });
});
