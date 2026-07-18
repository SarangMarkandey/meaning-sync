import { useEffect } from "react";

/** Reset the document viewport whenever a flow moves to a new screen. */
export function useScrollToTop(transitionKey: string) {
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [transitionKey]);
}
