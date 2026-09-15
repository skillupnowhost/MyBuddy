/** Three purpose-specific animated loading SVGs, used consistently everywhere something is
 * generating across the app: LoadingDots as the generic/default indicator, LoadingRings for
 * document generation, LoadingGrid for image/video generation. Each is a complete, trusted,
 * hardcoded SVG string (not user input) rendered via dangerouslySetInnerHTML — the animations
 * rely on inline <style>/<animate> tags that don't translate cleanly to individual JSX props.
 * A shared CSS rule (see globals.css's .loading-icon-raw) stretches the embedded <svg> to fill
 * whatever size the wrapper is given, regardless of each icon's own native width/height. */

const DOTS_SVG = `<svg width="60" height="60" viewBox="0 0 50 50"><circle cx="10" cy="25" r="2" fill="#60A5FA"><animate attributeName="cy" values="25;20;25;30;25" dur="1s" begin="0s" repeatCount="indefinite"></animate><animate attributeName="opacity" values="1;0.3;1" dur="1s" begin="0s" repeatCount="indefinite"></animate></circle><circle cx="18" cy="25" r="2" fill="#60A5FA"><animate attributeName="cy" values="25;20;25;30;25" dur="1s" begin="0.1s" repeatCount="indefinite"></animate><animate attributeName="opacity" values="1;0.3;1" dur="1s" begin="0.1s" repeatCount="indefinite"></animate></circle><circle cx="26" cy="25" r="2" fill="#60A5FA"><animate attributeName="cy" values="25;20;25;30;25" dur="1s" begin="0.2s" repeatCount="indefinite"></animate><animate attributeName="opacity" values="1;0.3;1" dur="1s" begin="0.2s" repeatCount="indefinite"></animate></circle><circle cx="34" cy="25" r="2" fill="#60A5FA"><animate attributeName="cy" values="25;20;25;30;25" dur="1s" begin="0.30000000000000004s" repeatCount="indefinite"></animate><animate attributeName="opacity" values="1;0.3;1" dur="1s" begin="0.30000000000000004s" repeatCount="indefinite"></animate></circle><circle cx="42" cy="25" r="2" fill="#60A5FA"><animate attributeName="cy" values="25;20;25;30;25" dur="1s" begin="0.4s" repeatCount="indefinite"></animate><animate attributeName="opacity" values="1;0.3;1" dur="1s" begin="0.4s" repeatCount="indefinite"></animate></circle></svg>`;

const RINGS_SVG = `<svg viewBox="0 0 240 240"><style>.pl1123__ring {
            animation: ringA 2s linear infinite;
        }

        .pl1123__ring--a {
            stroke: currentColor;
        }

        .pl1123__ring--b {
            animation-name: ringB;
            stroke: currentColor;
        }

        .pl1123__ring--c {
            animation-name: ringC;
            stroke: currentColor;
        }

        .pl1123__ring--d {
            animation-name: ringD;
            stroke: currentColor;
        }

        @keyframes ringA {
            from, 4% { stroke-dasharray: 0 660; stroke-width: 20; stroke-dashoffset: -330; }
            12% { stroke-dasharray: 60 600; stroke-width: 30; stroke-dashoffset: -335; }
            32% { stroke-dasharray: 60 600; stroke-width: 30; stroke-dashoffset: -595; }
            40%, 54% { stroke-dasharray: 0 660; stroke-width: 20; stroke-dashoffset: -660; }
            62% { stroke-dasharray: 60 600; stroke-width: 30; stroke-dashoffset: -665; }
            82% { stroke-dasharray: 60 600; stroke-width: 30; stroke-dashoffset: -925; }
            90%, to { stroke-dasharray: 0 660; stroke-width: 20; stroke-dashoffset: -990; }
        }

        @keyframes ringB {
            from, 12% { stroke-dasharray: 0 220; stroke-width: 20; stroke-dashoffset: -110; }
            20% { stroke-dasharray: 20 200; stroke-width: 30; stroke-dashoffset: -115; }
            40% { stroke-dasharray: 20 200; stroke-width: 30; stroke-dashoffset: -195; }
            48%, 62% { stroke-dasharray: 0 220; stroke-width: 20; stroke-dashoffset: -220; }
            70% { stroke-dasharray: 20 200; stroke-width: 30; stroke-dashoffset: -225; }
            90% { stroke-dasharray: 20 200; stroke-width: 30; stroke-dashoffset: -305; }
            98%, to { stroke-dasharray: 0 220; stroke-width: 20; stroke-dashoffset: -330; }
        }

        @keyframes ringC {
            from { stroke-dasharray: 0 440; stroke-width: 20; stroke-dashoffset: 0; }
            8% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -5; }
            28% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -175; }
            36%, 58% { stroke-dasharray: 0 440; stroke-width: 20; stroke-dashoffset: -220; }
            66% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -225; }
            86% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -395; }
            94%, to { stroke-dasharray: 0 440; stroke-width: 20; stroke-dashoffset: -440; }
        }

        @keyframes ringD {
            from, 8% { stroke-dasharray: 0 440; stroke-width: 20; stroke-dashoffset: 0; }
            16% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -5; }
            36% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -175; }
            44%, 50% { stroke-dasharray: 0 440; stroke-width: 20; stroke-dashoffset: -220; }
            58% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -225; }
            78% { stroke-dasharray: 40 400; stroke-width: 30; stroke-dashoffset: -395; }
            86%, to { stroke-dasharray: 0 440; stroke-width: 20; stroke-dashoffset: -440; }
        }</style><circle class="pl1123__ring pl1123__ring--a" cx="120" cy="120" r="105" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 660" stroke-dashoffset="-330" stroke-linecap="round"/><circle class="pl1123__ring pl1123__ring--b" cx="120" cy="120" r="35" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 220" stroke-dashoffset="-110" stroke-linecap="round"/><circle class="pl1123__ring pl1123__ring--c" cx="85" cy="120" r="70" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 440" stroke-linecap="round"/><circle class="pl1123__ring pl1123__ring--d" cx="155" cy="120" r="70" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 440" stroke-linecap="round"/></svg>`;

const GRID_SVG = `<svg version="1.1" id="cog9_1_" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px" viewBox="0 0 36 36" enable-background="new 0 0 96 96" xml:space="preserve"><style>.box5532 {
			fill:currentColor;
			transform-origin: 50% 50%;
		}

		@keyframes box5532-1 {
			9.0909090909% { transform: translate(-12px, 0); }
			18.1818181818% { transform: translate(0px, 0); }
			27.2727272727% { transform: translate(0px, 0); }
			36.3636363636% { transform: translate(12px, 0); }
			45.4545454545% { transform: translate(12px, 12px); }
			54.5454545455% { transform: translate(12px, 12px); }
			63.6363636364% { transform: translate(12px, 12px); }
			72.7272727273% { transform: translate(12px, 0px); }
			81.8181818182% { transform: translate(0px, 0px); }
			90.9090909091% { transform: translate(-12px, 0px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(1) { animation: box5532-1 4s infinite; }

		@keyframes box5532-2 {
			9.0909090909% { transform: translate(0, 0); }
			18.1818181818% { transform: translate(12px, 0); }
			27.2727272727% { transform: translate(0px, 0); }
			36.3636363636% { transform: translate(12px, 0); }
			45.4545454545% { transform: translate(12px, 12px); }
			54.5454545455% { transform: translate(12px, 12px); }
			63.6363636364% { transform: translate(12px, 12px); }
			72.7272727273% { transform: translate(12px, 12px); }
			81.8181818182% { transform: translate(0px, 12px); }
			90.9090909091% { transform: translate(0px, 12px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(2) { animation: box5532-2 4s infinite; }

		@keyframes box5532-3 {
			9.0909090909% { transform: translate(-12px, 0); }
			18.1818181818% { transform: translate(-12px, 0); }
			27.2727272727% { transform: translate(0px, 0); }
			36.3636363636% { transform: translate(-12px, 0); }
			45.4545454545% { transform: translate(-12px, 0); }
			54.5454545455% { transform: translate(-12px, 0); }
			63.6363636364% { transform: translate(-12px, 0); }
			72.7272727273% { transform: translate(-12px, 0); }
			81.8181818182% { transform: translate(-12px, -12px); }
			90.9090909091% { transform: translate(0px, -12px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(3) { animation: box5532-3 4s infinite; }

		@keyframes box5532-4 {
			9.0909090909% { transform: translate(-12px, 0); }
			18.1818181818% { transform: translate(-12px, 0); }
			27.2727272727% { transform: translate(-12px, -12px); }
			36.3636363636% { transform: translate(0px, -12px); }
			45.4545454545% { transform: translate(0px, 0px); }
			54.5454545455% { transform: translate(0px, -12px); }
			63.6363636364% { transform: translate(0px, -12px); }
			72.7272727273% { transform: translate(0px, -12px); }
			81.8181818182% { transform: translate(-12px, -12px); }
			90.9090909091% { transform: translate(-12px, 0px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(4) { animation: box5532-4 4s infinite; }

		@keyframes box5532-5 {
			9.0909090909% { transform: translate(0, 0); }
			18.1818181818% { transform: translate(0, 0); }
			27.2727272727% { transform: translate(0, 0); }
			36.3636363636% { transform: translate(12px, 0); }
			45.4545454545% { transform: translate(12px, 0); }
			54.5454545455% { transform: translate(12px, 0); }
			63.6363636364% { transform: translate(12px, 0); }
			72.7272727273% { transform: translate(12px, 0); }
			81.8181818182% { transform: translate(12px, -12px); }
			90.9090909091% { transform: translate(0px, -12px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(5) { animation: box5532-5 4s infinite; }

		@keyframes box5532-6 {
			9.0909090909% { transform: translate(0, 0); }
			18.1818181818% { transform: translate(-12px, 0); }
			27.2727272727% { transform: translate(-12px, 0); }
			36.3636363636% { transform: translate(0px, 0); }
			45.4545454545% { transform: translate(0px, 0); }
			54.5454545455% { transform: translate(0px, 0); }
			63.6363636364% { transform: translate(0px, 0); }
			72.7272727273% { transform: translate(0px, 12px); }
			81.8181818182% { transform: translate(-12px, 12px); }
			90.9090909091% { transform: translate(-12px, 0px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(6) { animation: box5532-6 4s infinite; }

		@keyframes box5532-7 {
			9.0909090909% { transform: translate(12px, 0); }
			18.1818181818% { transform: translate(12px, 0); }
			27.2727272727% { transform: translate(12px, 0); }
			36.3636363636% { transform: translate(0px, 0); }
			45.4545454545% { transform: translate(0px, -12px); }
			54.5454545455% { transform: translate(12px, -12px); }
			63.6363636364% { transform: translate(0px, -12px); }
			72.7272727273% { transform: translate(0px, -12px); }
			81.8181818182% { transform: translate(0px, 0px); }
			90.9090909091% { transform: translate(12px, 0px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(7) { animation: box5532-7 4s infinite; }

		@keyframes box5532-8 {
			9.0909090909% { transform: translate(0, 0); }
			18.1818181818% { transform: translate(-12px, 0); }
			27.2727272727% { transform: translate(-12px, -12px); }
			36.3636363636% { transform: translate(0px, -12px); }
			45.4545454545% { transform: translate(0px, -12px); }
			54.5454545455% { transform: translate(0px, -12px); }
			63.6363636364% { transform: translate(0px, -12px); }
			72.7272727273% { transform: translate(0px, -12px); }
			81.8181818182% { transform: translate(12px, -12px); }
			90.9090909091% { transform: translate(12px, 0px); }
			100% { transform: translate(0px, 0px); }
		}
		.box5532:nth-child(8) { animation: box5532-8 4s infinite; }

		@keyframes box5532-9 {
			9.0909090909% { transform: translate(-12px, 0); }
			18.1818181818% { transform: translate(-12px, 0); }
			27.2727272727% { transform: translate(0px, 0); }
			36.3636363636% { transform: translate(-12px, 0); }
			45.4545454545% { transform: translate(0px, 0); }
			54.5454545455% { transform: translate(0px, 0); }
			63.6363636364% { transform: translate(-12px, 0); }
			72.7272727273% { transform: translate(-12px, 0); }
			81.8181818182% { transform: translate(-24px, 0); }
			90.9090909091% { transform: translate(-12px, 0); }
			100% { transform: translate(0px, 0); }
		}
		.box5532:nth-child(9) { animation: box5532-9 4s infinite; }</style><g><rect class="box5532" x="13" y="1" rx="1" width="10" height="10"/><rect class="box5532" x="13" y="1" rx="1" width="10" height="10"/><rect class="box5532" x="25" y="25" rx="1" width="10" height="10"/><rect class="box5532" x="13" y="13" rx="1" width="10" height="10"/><rect class="box5532" x="13" y="13" rx="1" width="10" height="10"/><rect class="box5532" x="25" y="13" rx="1" width="10" height="10"/><rect class="box5532" x="1" y="25" rx="1" width="10" height="10"/><rect class="box5532" x="13" y="25" rx="1" width="10" height="10"/><rect class="box5532" x="25" y="25" rx="1" width="10" height="10"/></g></svg>`;

function RawSvgIcon({ svg, className, label }: { svg: string; className?: string; label: string }) {
  return (
    <span
      role="img"
      aria-label={label}
      className={`loading-icon-raw inline-block ${className ?? "h-6 w-6"}`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

/** The generic/default loading indicator — used anywhere something is working that isn't
 * specifically a document or an image/video generation. */
export function LoadingDots({ className }: { className?: string }) {
  return <RawSvgIcon svg={DOTS_SVG} className={className} label="Loading" />;
}

/** Document generation loading indicator. */
export function LoadingRings({ className }: { className?: string }) {
  return <RawSvgIcon svg={RINGS_SVG} className={className} label="Generating document" />;
}

/** Image / video generation loading indicator. */
export function LoadingGrid({ className }: { className?: string }) {
  return <RawSvgIcon svg={GRID_SVG} className={className} label="Generating media" />;
}
