"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = (window.localStorage.getItem("flash_theme") as "dark" | "light") || "dark";
    setTheme(saved);
    apply(saved);
  }, []);

  function apply(t: "dark" | "light") {
    document.documentElement.classList.toggle("dark", t === "dark");
  }
  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    apply(next);
    window.localStorage.setItem("flash_theme", next);
  }

  return (
    <Button variant="outline" size="icon" onClick={toggle} aria-label="Toggle theme">
      <Sun className="h-4 w-4 dark:hidden" />
      <Moon className="hidden h-4 w-4 dark:block" />
    </Button>
  );
}
