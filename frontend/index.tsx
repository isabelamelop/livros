import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Livros da Rafa — sua biblioteca pessoal" },
      { name: "description", content: "Busque e baixe livros de graça. Feito com carinho pra Rafa." },
    ],
  }),
  component: Index,
});

type BookOption = {
  command: string;
  title: string;
  author: string;
  language: string;
  format: string;
  size: string;
};

type SelectedFile = {
  download_url: string;
  filename: string;
};

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

function Index() {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<BookOption[]>([]);
  const [selected, setSelected] = useState<SelectedFile | null>(null);
  const [searching, setSearching] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    setOptions([]);
    setSelected(null);
    try {
      const res = await fetch(`${API_URL}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim() }),
      });
      if (!res.ok) throw new Error("Não consegui buscar agora 🥲");
      const data = (await res.json()) as { options: BookOption[] };
      setOptions(data.options ?? []);
      if (!data.options?.length) setError("Nada encontrado. Tenta outra palavra ✨");
    } catch (err: any) {
      setError(err?.message ?? "Erro inesperado");
    } finally {
      setSearching(false);
    }
  };

  const handleSelect = async (book: BookOption) => {
    setDownloading(book.command);
    setError(null);
    setSelected(null);
    try {
      const res = await fetch(`${API_URL}/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: book.command }),
      });
      if (!res.ok) throw new Error("Não encontrei o arquivo desse livro 😢");
      const data = (await res.json()) as { document: SelectedFile };
      const url = data.document.download_url.startsWith("http")
        ? data.document.download_url
        : `${API_URL}${data.document.download_url}`;
      setSelected({ ...data.document, download_url: url });
    } catch (err: any) {
      setError(err?.message ?? "Erro inesperado");
    } finally {
      setDownloading(null);
    }
  };

  return (
    <main className="relative mx-auto min-h-screen w-full max-w-5xl px-5 py-10 sm:py-16">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-20 -left-20 h-72 w-72 rounded-full bg-primary/20 blur-3xl animate-float" />
        <div className="absolute top-1/3 -right-24 h-80 w-80 rounded-full bg-accent/15 blur-3xl animate-float" style={{ animationDelay: "2s" }} />
      </div>

      <header className="mb-12 text-center animate-fade-up">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-card/40 px-4 py-1.5 text-xs font-medium text-muted-foreground backdrop-blur-md">
          <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
          Feito com carinho pra Rafa
        </div>
        <h1 className="text-5xl font-semibold leading-[1.05] sm:text-7xl">
          A biblioteca <span className="text-gradient italic">da Rafa</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-base text-muted-foreground sm:text-lg">
          Busque qualquer livro do universo e baixe de graça. 🩷
        </p>
      </header>

      <section className="glass-card mb-10 rounded-3xl p-6 sm:p-8 animate-fade-up" style={{ animationDelay: "80ms" }}>
        <div className="mb-5 flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-primary/15 text-primary">🔍</span>
          <div>
            <h2 className="text-xl font-semibold">O que cê quer ler hoje?</h2>
            <p className="text-sm text-muted-foreground">Busque por título, autor ou tema.</p>
          </div>
        </div>
        <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tipo: Clarice Lispector, A Hora da Estrela..."
            className="flex-1 rounded-2xl border border-border bg-input/60 px-5 py-4 text-base text-foreground placeholder:text-muted-foreground/70 outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/20"
          />
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="btn-hero inline-flex items-center justify-center gap-2 rounded-2xl px-7 py-4 text-base disabled:opacity-60 hover:[transform:translateY(-2px)]"
          >
            {searching ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                Procurando
              </>
            ) : (
              <>Buscar →</>
            )}
          </button>
        </form>
        {error && (
          <p className="mt-4 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive-foreground">
            {error}
          </p>
        )}
      </section>

      <section className="mb-10 animate-fade-up" style={{ animationDelay: "160ms" }}>
        <div className="mb-5 flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-semibold sm:text-3xl">
              <span className="text-gradient">Sugestões</span> pra você
            </h2>
            <p className="text-sm text-muted-foreground">Todas as opções do universo 🌺</p>
          </div>
          {options.length > 0 && (
            <span className="hidden text-xs uppercase tracking-widest text-muted-foreground sm:block">
              {options.length} {options.length === 1 ? "opção" : "opções"}
            </span>
          )}
        </div>

        {options.length === 0 ? (
          <div className="glass-card rounded-3xl p-10 text-center text-muted-foreground">
            {searching ? "Procurando no universo..." : "Faz uma busca aí em cima ✨"}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {options.map((book) => {
              const isLoading = downloading === book.command;
              return (
                <button
                  key={book.command}
                  onClick={() => handleSelect(book)}
                  disabled={isLoading || downloading !== null}
                  className="glass-card group relative overflow-hidden rounded-3xl p-6 text-left transition-all duration-300 hover:-translate-y-1 disabled:opacity-60"
                >
                  <div className="absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    {book.format && (
                      <span className="rounded-full bg-primary/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-primary">
                        {book.format}
                      </span>
                    )}
                    {book.size && (
                      <span className="rounded-full bg-secondary px-3 py-1 text-[11px] font-medium text-muted-foreground">
                        {book.size}
                      </span>
                    )}
                    {book.language && book.language !== "—" && (
                      <span className="rounded-full bg-accent/15 px-3 py-1 text-[11px] font-medium text-accent">
                        🌐 {book.language}
                      </span>
                    )}
                    <span className="ml-auto text-2xl opacity-70 transition group-hover:scale-110 group-hover:opacity-100">
                      {isLoading ? "⏳" : "📖"}
                    </span>
                  </div>
                  <h3 className="font-display text-xl font-semibold leading-tight text-foreground">
                    {book.title}
                  </h3>
                  <p className="mt-1 text-sm italic text-muted-foreground">por {book.author}</p>
                  <p className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-primary opacity-80 group-hover:opacity-100">
                    {isLoading ? "Preparando download..." : "Baixar este →"}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="glass-card relative overflow-hidden rounded-3xl p-8 animate-fade-up sm:p-10" style={{ animationDelay: "240ms" }}>
        <div aria-hidden className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-primary/20 blur-3xl" />
        <div className="relative">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-accent/20 text-xl">⬇️</span>
            <h2 className="text-2xl font-semibold sm:text-3xl">Seu livro</h2>
          </div>

          {selected ? (
            <div>
              <p className="text-sm uppercase tracking-widest text-muted-foreground">Pronto pra baixar</p>
              <h3 className="font-display text-3xl font-semibold text-foreground sm:text-4xl">
                {selected.filename}
              </h3>
              <a
                href={selected.download_url}
                download={selected.filename}
                className="btn-hero mt-6 inline-flex items-center gap-2 rounded-2xl px-7 py-4 text-base hover:[transform:translateY(-2px)]"
              >
                Baixar agora ✨
              </a>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-border bg-background/30 p-8 text-center">
              <p className="text-3xl">🌷</p>
              <p className="mt-2 text-muted-foreground">
                Clica numa opção lá em cima e seu livro aparece aqui.
              </p>
            </div>
          )}
        </div>
      </section>

      <footer className="mt-12 text-center text-xs text-muted-foreground/70">
        feito com 🩷 pra Rafa · boa leitura sempre
      </footer>
    </main>
  );
}
