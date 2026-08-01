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
	define: {
		// Expose environment variables to the client
		'import.meta.env.GOOGLE_MAPS_API_KEY': JSON.stringify(process.env.GOOGLE_MAPS_API_KEY),
		'import.meta.env.TOSS_CLIENT_KEY': JSON.stringify(process.env.TOSS_CLIENT_KEY),
		'import.meta.env.PAYPAL_CLIENT_ID': JSON.stringify(process.env.PAYPAL_CLIENT_ID)
	},
	plugins: [
		paraglide({
			project: './project.inlang',
			outdir: './src/lib/paraglide'
		}),
		sveltekit()
	]
});
