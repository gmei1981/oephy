function pn = pn_gen_1f3(N,fs,l_1m_dbc,floor_dbc,slope_db,f_tbl,l_tbl)
% pn_gen_1f3 — colored oscillator phase-noise sequence (1/f^n + floor).
%
%   Target single-sided PSD in dBc/Hz, single-slope mode (default):
%       L(f) = max( floor_dbc , l_1m_dbc + slope_db*log10(1e6/f) )
%   i.e. a slope_db dB/dec line through (1 MHz, l_1m_dbc), capped at the
%   white floor (slope 30 = 1/f^3, 10 = 1/f).  Frequency-domain synthesis
%   with random phase, conjugate-symmetric spectrum -> real sequence;
%   scaling verified in check_units (measured PSD vs target within ~1 dB).
%
%   Piecewise mode (optional f_tbl/l_tbl, >=2 points, monotonically up):
%       L(f) log-log interpolated through (f_tbl, l_tbl), end slopes
%       extrapolated outside the table — use for measured multi-knee PN
%       specs (e.g. 100k/-76, 1M/-105, 10M/-129, 100M/-151 dBc/Hz).
%
%   Returns pn in RADIANS (length N, sampled at fs).  Add to the carrier
%   phase directly (this is absolute phase noise, not a frequency sequence).
%   Content below fs/N (the run length) and above fs/2 is not represented
%   (wideband folding of real ~GHz-rate noise onto the fs sampling grid is
%   not modeled — document when comparing spot-noise numbers).

if nargin<5, slope_db = 30; end
f = (0:floor(N/2))'*fs/N;                 % one-sided bin frequencies
if nargin>=6 && ~isempty(f_tbl)
    L = interp1(log10(f_tbl(:)), l_tbl(:), log10(max(f,f(2))), 'linear','extrap');
else
    L = l_1m_dbc + slope_db*log10(1e6./max(f,f(2)));
    L = max(L, floor_dbc);
end
S = 10.^(L/10) * 2;                       % rad^2/Hz, one-sided

X = complex(zeros(N,1));
mag2 = S * N * fs;                        % E|X(k)|^2  (two-sided bins)
for k = 2:N/2
    X(k)   = sqrt(mag2(k)/2) * (randn + 1i*randn);
    X(N-k+2) = conj(X(k));
end
X(N/2+1) = sqrt(mag2(N/2+1)) * randn;     % Nyquist bin (real)
pn = real(ifft(X));                        % radians
end
