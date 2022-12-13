document.addEventListener("DOMContentLoaded", function () {
    document.body.innerHTML = document.body.innerHTML
            .replace(/<\/em>[\n^<]*em>/g, '')
            .replace(/Union\[jax\.numpy\.lax_numpy\.ndarray, jax.interpreters\.xla\.DeviceArray(, jax\.interpreters\.pxla\.ShardedDeviceArray)?]/g, 'objax.JaxArray');
});
