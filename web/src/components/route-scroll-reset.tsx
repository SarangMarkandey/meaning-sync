"use client";

import { usePathname } from "next/navigation";

import { useScrollToTop } from "@/lib/use-scroll-to-top";

export function RouteScrollReset() {
  const pathname = usePathname();
  useScrollToTop(`route:${pathname}`);
  return null;
}
