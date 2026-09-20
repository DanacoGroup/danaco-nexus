// Kaskada wejścia: kolejne dzieci dostają opóźnienie --stagger-step, najwyżej --stagger-max
// kroków (motion, rozdz. 5). Elementy od piątego wchodzą razem z czwartym.

import { Children, cloneElement, isValidElement, type CSSProperties, type ReactNode } from "react";
import { cx, type BaseProps } from "./types";

const MAKS_KROKOW = 4;

export interface StaggerProps extends BaseProps {
  as?: "div" | "ul" | "ol" | "section";
  children: ReactNode;
}

export function opoznienieKaskady(index: number): CSSProperties {
  const krok = Math.min(index, MAKS_KROKOW);
  return { "--ui-opoznienie": `calc(var(--stagger-step) * ${krok})` } as CSSProperties;
}

export function Stagger({ as: Element = "div", className, children, ...reszta }: StaggerProps) {
  const dzieci = Children.toArray(children).map((dziecko, index) => {
    if (!isValidElement<{ className?: string; style?: CSSProperties }>(dziecko)) return dziecko;
    return cloneElement(dziecko, {
      className: cx(dziecko.props.className, "ui-wejscie"),
      style: { ...opoznienieKaskady(index), ...dziecko.props.style },
    });
  });

  return (
    <Element className={className} {...reszta}>
      {dzieci}
    </Element>
  );
}
