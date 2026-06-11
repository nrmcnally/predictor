import { useEffect, useRef, useState } from "react";
import { searchFighters } from "../api/client.js";

export default function FighterSearchInput({
  value,
  onChange,
  onSelect,
  placeholder = "Search fighters…",
  corner,
  id,
}) {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const debounceRef = useRef(0);
  const wrapRef = useRef(null);

  useEffect(() => {
    function handlePointerDown(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  function runSearch(query) {
    window.clearTimeout(debounceRef.current);

    if (!query.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }

    debounceRef.current = window.setTimeout(async () => {
      try {
        const fighters = await searchFighters(query, 8);
        setResults(fighters);
        setOpen(fighters.length > 0);
        setActiveIndex(-1);
      } catch {
        setResults([]);
        setOpen(false);
      }
    }, 180);
  }

  function selectFighter(name) {
    setOpen(false);
    setResults([]);
    onSelect ? onSelect(name) : onChange(name);
  }

  function handleKeyDown(event) {
    if (!open || results.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index - 1 + results.length) % results.length);
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectFighter(results[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className={`search-input ${corner ? `corner-${corner}` : ""}`} ref={wrapRef}>
      <input
        id={id}
        type="text"
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck="false"
        onChange={(event) => {
          onChange(event.target.value);
          runSearch(event.target.value);
        }}
        onFocus={() => {
          if (results.length > 0) {
            setOpen(true);
          }
        }}
        onKeyDown={handleKeyDown}
      />

      {open && (
        <ul className="search-results" role="listbox">
          {results.map((name, index) => (
            <li key={name}>
              <button
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={index === activeIndex ? "active" : ""}
                onClick={() => selectFighter(name)}
              >
                {name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
