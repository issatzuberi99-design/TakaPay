const locationButton = document.querySelector("#location-button");
const locationStatus = document.querySelector("#location-status");
const latitudeInput = document.querySelector("#id_latitude");
const longitudeInput = document.querySelector("#id_longitude");
const accuracyInput = document.querySelector("#id_location_accuracy");

locationButton?.addEventListener("click", () => {
    if (!navigator.geolocation) {
        locationStatus.textContent = "Location is not available in this browser.";
        return;
    }

    locationButton.disabled = true;
    locationStatus.textContent = "Requesting your location...";
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const { latitude, longitude, accuracy } = position.coords;
            latitudeInput.value = latitude.toFixed(6);
            longitudeInput.value = longitude.toFixed(6);
            accuracyInput.value = accuracy.toFixed(2);
            locationStatus.textContent = `Location captured: Latitude ${latitude.toFixed(6)}, Longitude ${longitude.toFixed(6)}, Accuracy ${accuracy.toFixed(2)} meters.`;
            locationButton.disabled = false;
        },
        () => {
            locationStatus.textContent = "Location permission was denied or unavailable. Please allow GPS access and try again.";
            locationButton.disabled = false;
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
});