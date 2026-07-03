import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog.jsx";

const baseProps = {
  open: true,
  title: "Delete user?",
  body: "This cannot be undone.",
  confirmLabel: "Delete",
  onConfirm: () => {},
  onCancel: () => {},
};

test("renders nothing when closed", () => {
  const { container } = render(<ConfirmDialog {...baseProps} open={false} />);
  expect(container).toBeEmptyDOMElement();
  expect(document.querySelector(".modal")).toBeNull();
});

test("shows title/body and focuses Cancel (safe default)", () => {
  render(<ConfirmDialog {...baseProps} />);
  expect(screen.getByRole("alertdialog", { name: "Delete user?" })).toBeInTheDocument();
  expect(screen.getByText("This cannot be undone.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
});

test("confirm and cancel fire their callbacks", () => {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(<ConfirmDialog {...baseProps} onConfirm={onConfirm} onCancel={onCancel} />);

  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(onConfirm).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onCancel).toHaveBeenCalledTimes(1);
});

test("Escape and scrim-click cancel; busy disables confirm", () => {
  const onCancel = vi.fn();
  render(<ConfirmDialog {...baseProps} onCancel={onCancel} busy />);

  fireEvent.keyDown(window, { key: "Escape" });
  expect(onCancel).toHaveBeenCalledTimes(1);

  fireEvent.click(document.querySelector(".modal-scrim"));
  expect(onCancel).toHaveBeenCalledTimes(2);

  // busy: the confirm button shows an ellipsis and is disabled
  expect(screen.getByRole("button", { name: "…" })).toBeDisabled();
});
