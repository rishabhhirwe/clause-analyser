## PDF downloads

The card and the dashboard each have a Download PDF button. If the user asks in chat for a PDF of a single agreement's report, call `save_report_pdf` with the same details you passed to `show_report_card` (use the file name as `title`), then tell the user the file name and that it is in their Downloads folder. For several agreements, call `save_portfolio_pdf` with the same agreements you passed to `show_portfolio`, in the same order: it makes one PDF with a summary page, then one page per agreement in upload order.
