document.addEventListener("DOMContentLoaded", () => {
  const jukeboxButton = document.getElementById("jukebox-easter-egg");
  const jukeboxAudio = document.getElementById("jukebox-audio");

  if (!jukeboxButton || !jukeboxAudio) return;

  const stateKey = "jukebox-easter-egg-state";
  const maxPlaySeconds = 15;

  let stopTimer = null;

  function setPlayingUi(isPlaying) {
    jukeboxButton.classList.toggle("is-playing", isPlaying);
    jukeboxButton.setAttribute(
      "aria-label",
      isPlaying ? "Zastavit easter egg" : "Přehrát easter egg"
    );
  }

  function getState() {
    try {
      return JSON.parse(localStorage.getItem(stateKey));
    } catch {
      return null;
    }
  }

  function saveState(isPlaying) {
    localStorage.setItem(
      stateKey,
      JSON.stringify({
        isPlaying,
        currentTime: jukeboxAudio.currentTime,
        savedAt: Date.now(),
      })
    );
  }

  function clearStopTimer() {
    if (!stopTimer) return;

    clearTimeout(stopTimer);
    stopTimer = null;
  }

  function stopMusic() {
    clearStopTimer();

    jukeboxAudio.pause();
    jukeboxAudio.currentTime = 0;

    setPlayingUi(false);
    saveState(false);
  }

  function scheduleStop() {
    clearStopTimer();

    const remainingSeconds = maxPlaySeconds - jukeboxAudio.currentTime;
    const remainingMs = Math.max(remainingSeconds * 1000, 0);

    stopTimer = setTimeout(stopMusic, remainingMs);
  }

  async function playMusic(fromBeginning = false) {
    if (fromBeginning) {
      jukeboxAudio.currentTime = 0;
    }

    if (jukeboxAudio.currentTime >= maxPlaySeconds) {
      jukeboxAudio.currentTime = 0;
    }

    try {
      await jukeboxAudio.play();
      setPlayingUi(true);
      saveState(true);
      scheduleStop();
    } catch {
      setPlayingUi(false);
      saveState(false);
    }
  }

  jukeboxButton.addEventListener("click", () => {
    if (jukeboxAudio.paused) {
      playMusic(true);
    } else {
      stopMusic();
    }
  });

  jukeboxAudio.addEventListener("timeupdate", () => {
    if (!jukeboxAudio.paused) {
      saveState(true);
    }

    if (jukeboxAudio.currentTime >= maxPlaySeconds) {
      stopMusic();
    }
  });

  jukeboxAudio.addEventListener("ended", () => {
    stopMusic();
  });

  window.addEventListener("beforeunload", () => {
    saveState(!jukeboxAudio.paused);
  });

  const savedState = getState();

  if (
    savedState &&
    savedState.isPlaying &&
    savedState.currentTime < maxPlaySeconds
  ) {
    jukeboxAudio.currentTime = savedState.currentTime;
    playMusic(false);
  } else {
    setPlayingUi(false);
  }
});