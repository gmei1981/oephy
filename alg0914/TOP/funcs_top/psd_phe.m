function [f,L] = psd_phe(phe,fs)
% psd_phe — one-sided PSD of the phase-error sequence, as S_phi/2 (dBc/Hz).
%   phe : phase error in DCO cycles (mean removed)
%   fs  : sample rate (fref)
%   Returns f [Hz] and L [dBc/Hz].  Uses pwelch when the Signal Processing
%   Toolbox is present; otherwise a hand-rolled Welch estimator with the
%   same parameters (Hann window, 50% overlap).

nfft = 2^13;
win = hann_local(nfft);
nseg = floor((length(phe)-nfft/2)/(nfft/2));
if nseg < 4
    nfft = 2^10;
    win = hann_local(nfft);
    nseg = floor((length(phe)-nfft/2)/(nfft/2));
end
if nseg < 2
    nseg = 1;
end

if exist('pwelch','file')==2
    [Pxx,f] = pwelch(phe-mean(phe),win,nfft/2,nfft,fs);
else
    % manual Welch, Hann, 50% overlap
    step = nfft/2;
    phe = phe(:) - mean(phe);
    acc = zeros(nfft,1);
    U = sum(win.^2);
    for k=1:nseg
        seg = phe((k-1)*step+1 : (k-1)*step+nfft) .* win;
        acc = acc + abs(fft(seg,nfft)).^2;
    end
    Pxx = acc / (nseg * U * fs);
    Pxx = Pxx(1:nfft/2+1);
    Pxx(2:end-1) = 2*Pxx(2:end-1);        % one-sided
    f = (0:nfft/2)' * fs/nfft;
end

Sphi = (2*pi)^2 * Pxx;                    % cycles -> radians
L = 10*log10(Sphi/2);
end

function w = hann_local(n)
w = 0.5 - 0.5*cos(2*pi*(0:n-1)'/(n-1));
end
