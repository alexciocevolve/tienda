import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom is not a browser: it has no layout, so it has no idea what is on screen and does
// not implement IntersectionObserver at all.
//
// The stand-in below reports "visible" as soon as something is observed, which is what a
// real browser does when the element is already in view - and it is what makes the
// catalog load its first page without anybody scrolling. The notification is sent
// asynchronously, like the real one, so React has finished rendering before it arrives.
// A test therefore sees the catalog behave as it does on a tall screen: it keeps asking
// for the next page until the server says there is not one.
//
// Written as a plain function, not a `class`, on purpose: `new` on a function that
// returns an object gives back that object, so this works, and the project's rule about
// having no classes in frontend/src holds in the tests too.
vi.stubGlobal("IntersectionObserver", function fakeIntersectionObserver(
  callback: IntersectionObserverCallback,
) {
  return {
    observe: () =>
      queueMicrotask(() => callback([{ isIntersecting: true }] as never, null as never)),
    unobserve: () => {},
    disconnect: () => {},
    takeRecords: () => [],
    root: null,
    rootMargin: "",
    thresholds: [],
  };
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});
