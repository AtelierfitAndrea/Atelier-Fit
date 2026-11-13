export const ResultNote = ({ testid = "result-note", notice }) => (
  <>
    {notice && <p className="mt-2 text-sm text-[#8C7355]" data-testid={`${testid}-notice`}>{notice}</p>}
    <p className="mt-2 text-sm text-[#6B5B4B]" data-testid={testid}>Prova generata - dimmi cosa correggere</p>
  </>
);
