/** Soft, slow-drifting gradient blobs used behind the centered "card list" tool pages, echoing
 * the indigo/violet gradient language from the homepage wordmark without competing with content.
 * Purely decorative (aria-hidden) and disabled under reduced-motion. */
export default function PageBlobBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="animate-blob-drift absolute -left-24 -top-32 h-72 w-72 rounded-full bg-indigo-200/30 blur-3xl" />
      <div className="animate-blob-drift absolute -right-24 top-1/3 h-96 w-96 rounded-full bg-violet-200/25 blur-3xl [animation-delay:-6s]" />
      <div className="animate-blob-drift absolute -bottom-24 left-1/4 h-72 w-72 rounded-full bg-sky-100/30 blur-3xl [animation-delay:-12s]" />
    </div>
  );
}
