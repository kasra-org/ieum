import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { paraglide } from '@inlang/paraglide-js-adapter-sveltekit/vite';

const ALLOWED_HOST = process.env.ALLOWED_HOST || 'localhost'

export default defineConfig({
	// @lucide/svelte exposes its Svelte sources only through the `svelte` export
	// condition, without the legacy top-level `svelte` field that
	// vite-plugin-svelte keys auto-bundling off. Without this it stays external
	// during SSR and Node is handed a raw .svelte file:
	//   Unknown file extension ".svelte" ... @lucide/svelte/dist/Icon.svelte
	ssr: {
		noExternal: ['@lucide/svelte']
	},
	server: {
		allowedHosts: [ALLOWED_HOST, ],
		watch: {
			// Watch the messages directory for changes
			ignored: ['!**/messages/**']
		}
	},
	// These three are browser-side keys and must reach the client. `define` only
	// substituted them during `vite build`; under `vite dev` import.meta.env is a
	// live object that define does not touch, so the map fell back to its
	// 'YOUR_GOOGLE_MAPS_API_KEY' placeholder and Google served a watermarked
	// "development purposes only" map. envPrefix applies in both modes.
	//
	// Listed as exact names, NOT as 'TOSS_'/'PAYPAL_' prefixes: TOSS_SECRET_KEY
	// and PAYPAL_SECRET_KEY exist, and a broad prefix would inline those secrets
	// into the public bundle.
	envPrefix: [
		'VITE_',
		'GOOGLE_MAPS_API_KEY',
		'TOSS_CLIENT_KEY',
		'PAYPAL_CLIENT_ID'
	],
	plugins: [
		paraglide({
			project: './project.inlang',
			outdir: './src/lib/paraglide'
		}),
		sveltekit()
	]
});
