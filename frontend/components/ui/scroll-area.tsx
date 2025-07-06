import * as React from "react"
import { cn } from "@/lib/utils"

export interface ScrollAreaProps {
  children: React.ReactNode
  className?: string
  style?: React.CSSProperties
}

const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ children, className, style }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "relative overflow-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100",
          className
        )}
        style={style}
      >
        {children}
      </div>
    )
  }
)
ScrollArea.displayName = "ScrollArea"

export { ScrollArea } 