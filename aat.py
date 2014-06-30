"""
This file contains functions for targeting objects as part of the SAGA Survey's
AAT observations.
"""
import numpy as np

import targeting
from astropy import units as u
from astropy.coordinates import Angle


def prioritize_targets(targets, rvir=300*u.kpc):
    rvkpc = rvir.to(u.kpc).value

    g = targets['g']
    r = targets['r']
    i = targets['i']
    rkpc = targets['rhost_kpc']

    pris = np.zeros(len(targets), dtype=int)


    pris[(g-r < 1.2) & (r-i < 0.7) & (r<21)] = 1
    pris[(g-r < 1.0) & (r-i < 0.5) & (r<21)] = 2

    pris[(g-r < 1.2) & (r-i < 0.7) & (r<20.5)] = 3
    pris[(g-r < 1.0) & (r-i < 0.5) & (r<20.5)] = 4

    pris[(g-r < 1.2) & (r-i < 0.7) & (r<21) & (rkpc < rvkpc)] = 5
    pris[(g-r < 1.0) & (r-i < 0.5) & (r<21) & (rkpc < rvkpc)] = 6

    pris[(g-r < 1.2) & (r-i < 0.7) & (r<20.5) & (rkpc < rvkpc)] = 7
    pris[(g-r < 1.0) & (r-i < 0.5) & (r<20.5) & (rkpc < rvkpc)] = 8

    return pris


def produce_master_fld(host, utcobsdate, catalog, pris, guidestars,
                       fluxstars, skyradec, outfn=None, randomizeorder=True):
    """
    Rank of 1 to 9 means use (9 highest), others skipped
    """
    lines = []
    lines.append('LABEL ' + host.name + ' base catalog')
    lines.append('UTDATE  {yr} {mo:02} {day:02}'.format(yr=utcobsdate.year,
                                                        mo=utcobsdate.month,
                                                        day=utcobsdate.day))
    censtr = host.coords.to_string('hmsdms', sep=' ', precision=2, alwayssign=True)[1:]  # strips the leading '+'
    lines.append('CENTRE  ' + censtr)
    lines.append('EQUINOX J2000.0')
    #lines.append('WLEN1 3700')
    #lines.append('WLEN2 8800')
    lines.append('# End of Header')
    lines.append('')
    lines.append('# TargetName(unique for header) RA(h m s) Dec(d m s) TargetType(Program,Fiducial,Sky) Priority(9 is highest) Magnitude 0 TargetName')

    if randomizeorder:
        idxs = np.random.permutation(len(catalog))
    else:
        idxs = np.arange(len(catalog))

    for ci, pri in zip(catalog[idxs], pris[idxs]):
        if not 1 <= pri <= 9:
            continue

        entry = []

        entry.append(str(ci['objID']))
        entry.append(Angle(ci['ra'], u.deg).to(u.hourangle).to_string(sep=' ', precision=2))
        entry.append(Angle(ci['dec'], u.deg).to_string(sep=' ', alwayssign=True, precision=2))
        entry.append('P')
        entry.append(str(pri))
        entry.append('{0:0.2f}'.format(ci['fiber2mag_r']))
        entry.append('0')
        entry.append('magcol=fiber2mag_r, model_r={0:.2f}'.format(ci['r']))

        lines.append(' '.join(entry))

    lines.append('\n#Flux stars')
    if randomizeorder:
        idxs = np.random.permutation(len(fluxstars))
    else:
        idxs = np.arange(len(fluxstars))
    for idx, fxs in enumerate(fluxstars[idxs]):
        entry = []

        entry.append('Flux' + str(idx))
        entry.append(Angle(fxs['ra'], u.deg).to(u.hourangle).to_string(sep=' ', precision=2))
        entry.append(Angle(fxs['dec'], u.deg).to_string(sep=' ', alwayssign=True, precision=2))
        entry.append('P')
        entry.append('9')
        entry.append('{0:0.2f}'.format(fxs['r']))
        entry.append('0')
        entry.append('id=' + str(fxs['objID']))

        lines.append(' '.join(entry))

    lines.append('\n#Guide stars')
    if randomizeorder:
        idxs = np.random.permutation(len(guidestars))
    else:
        idxs = np.arange(len(guidestars))
    for idx, g in enumerate(guidestars[idxs]):
        entry = []

        entry.append('Guide' + str(idx))
        entry.append(Angle(g['ra'], u.deg).to(u.hourangle).to_string(sep=' ', precision=2))
        entry.append(Angle(g['dec'], u.deg).to_string(sep=' ', alwayssign=True, precision=2))
        entry.append('F')
        entry.append('9')
        entry.append('{0:0.2f}'.format(g['r']))
        entry.append('0')
        entry.append('id=' + str(g['objID']))

        lines.append(' '.join(entry))

    lines.append('\n#Sky positions')
    if randomizeorder:
        idxs = np.random.permutation(len(skyradec[0]))
    else:
        idxs = np.arange(len(skyradec[0]))
    skyradeczip = np.array(zip(*skyradec))
    for idx, (ra, dec) in enumerate(skyradeczip[idxs]):
        entry = []

        entry.append('Sky' + str(idx))
        entry.append(Angle(ra, u.deg).to(u.hourangle).to_string(sep=' ', precision=2))
        entry.append(Angle(dec, u.deg).to_string(sep=' ', alwayssign=True, precision=2))
        entry.append('S')
        entry.append('9')
        entry.append('20.00')
        entry.append('0')
        entry.append('sky')

        lines.append(' '.join(entry))

    if outfn is not None:
        with open(outfn, 'w') as f:
            for l in lines:
                f.write(l)
                f.write('\n')
    return lines


def subsample_from_master_fld(masterfn, outfn, nperpri, nguides='all',
                              nflux='all', nsky='all', utcobsdate=None):
    """
    Selects from the master .fld and creates a smaller .fld file for consumption
    by configure.

    nperpri maps pri numbers to the number to do (any missing are
    treated as 0)
    """

    inhdr = True

    skydone = fluxdone = guidesdone = 0
    pridone = dict([(i, 0) for i in range(10) if i != 0])

    with open(masterfn) as fr:
        with open(outfn, 'w') as fw:
            for l in fr:
                if inhdr:
                    if l.startswith('LABEL'):
                        fw.write(l.replace('base catalog', 'subsampled'))
                    elif l.startswith('UTDATE'):
                        if utcobsdate is None:
                            fw.write(l)
                        else:
                            s = 'UTDATE  {yr} {mo:02} {day:02}\n'
                            fw.write(s.format(yr=utcobsdate.year,
                                              mo=utcobsdate.month,
                                              day=utcobsdate.day))
                    else:
                        fw.write(l)

                    if l.startswith('# End of Header'):
                        inhdr = False

                else:  # not in header
                    lst = l.strip()
                    if lst == '' or lst.startswith('#'):
                        fw.write(l)
                    elif l.startswith('Guide'):
                        if nguides == 'all' or (guidesdone < nguides):
                            fw.write(l)
                            guidesdone += 1
                    elif l.startswith('Flux'):
                        if nflux == 'all' or (fluxdone < nflux):
                            fw.write(l)
                            fluxdone += 1
                    elif l.startswith('Sky'):
                        if nsky == 'all' or (skydone < nsky):
                            fw.write(l)
                            skydone += 1
                    else:  # program target
                        ls = l.split()
                        pri = int(ls[8])
                        ntodo = nperpri.get(pri, 0)
                        if pridone[pri] < nperpri.get(pri, 0):
                            fw.write(l)
                            pridone[pri] += 1


def imagelist_fld_targets(fldlinesorfn, ttype='all', **kwargs):
    from targeting import sampled_imagelist

    if isinstance(fldlinesorfn, basestring):
        with open(fldlinesorfn) as f:
            fldlines = f.read().split('\n')
    else:
        fldlines = fldlinesorfn

    prognum = -1
    if ttype.startswith('prog'):
        if ttype[4:] == '':
            prognum = int(ttype[4:])
        else:
            prognum = 0

    ras = []
    decs = []
    names = []
    for l in fldlines:
        if l.startswith('#') or l.startswith('*') or l.strip() == '':
            continue

        ls = l.split()
        if len(ls) > 9:
            if (ttype == 'all' or
               (ttype == 'sky' and ls[7] == 'S') or
               (ttype == 'guide' and ls[7] == 'F') or
               (ttype == 'flux' and ls[7] == 'P' and ls[0].startswith('Flux')) or
               (prognum>-1 and ls[7] == 'P' and not ls[0].startswith('Flux') and (prognum==0 or prognum==int(ls[8])))
               ):
                ras.append(Angle(ls[1]+'h'+ls[2]+'m'+ls[3]+'s').deg)
                decs.append(Angle(ls[4]+'d'+ls[5]+'m'+ls[6]+'s').deg)
                names.append(ls[0])

    kwargs['names'] = names
    return sampled_imagelist(ras, decs, **kwargs)


def select_guide_stars_usnob(host, faintlimit=13.5, brightlimit=12., randomize=True):
    """
    Selects candidate FOP stars from USNO-B

    Parameters
    ----------
    host : NSAHost
    faintlimit : number
    brightlimit : number
    randomize : bool
        Randomize the order of the catalog and the very end

    Returns
    -------
        cat : table
            The USNO-B catalog with the selection applied
    """

    cat = host.get_usnob_catalog()

    mag = cat['R2']

    magcuts = (brightlimit < mag) & (mag < faintlimit)

    # only take things with *both* R mags
    bothRs = (cat['R1'] != 0) & (cat['R2'] != 0)

    res = cat[bothRs & magcuts]
    if randomize:
        res = res[np.random.permutation(len(res))]

    return res

def select_guide_stars_sdss(cat, magrng=(13.5, 14)):
    msk = cat['type'] == 6 #type==6 means star

    magrng = min(*magrng), max(*magrng)

    msk = msk & (magrng[0] < cat['r']) & (cat['r'] < magrng[1])

    return cat[msk]

def select_sky_positions(host, nsky=250, sdsscat=None, usnocat=None, nearnesslimitarcsec=15):
    """
    Produces sky positions uniformly covering a circle centered at the host

    Parameters
    ----------
    host : NSAHost
    sdsscat
    usnocat
    nsky : int
        Number of sky positions to generate

    Returns
    -------
    ra : array
    dec : array
    """
    from scipy.spatial import cKDTree

    if sdsscat is None:
        sdsscat = host.get_sdss_catalog()
    if usnocat is None:
        usnocat = host.get_usnob_catalog()

    neardeg = nearnesslimitarcsec / 3600.

    skdt = cKDTree(np.array([sdsscat['ra'], sdsscat['dec']]).T)
    ukdt = cKDTree(np.array([usnocat['RA'], usnocat['DEC']]).T)

    raddeg = host.environsarcmin / 60.

    ras = np.array([])
    decs = np.array([])

    i = -1
    while len(ras) < nsky:
        i += 1

        rs = raddeg * 2 * np.arccos(np.random.rand(nsky)) / np.pi
        thetas = 2 * np.pi * np.random.rand(nsky)

        ra = host.ra + rs * np.sin(thetas)
        dec = host.dec + rs * np.cos(thetas)

        dsdss = skdt.query(np.array([ra, dec]).T)[0]
        dusno = ukdt.query(np.array([ra, dec]).T)[0]

        msk = (dsdss > neardeg) & (dusno > neardeg)

        ras = np.append(ras, ra[msk])
        decs = np.append(decs, dec[msk])

        if i > 100:
            raise ValueError('Could not produce {nsky} sky positions after {i} iterations!'.format(nsky=nsky, i=i))

    return ras[:nsky], decs[:nsky]


def select_flux_stars(cat, magrng=(17, 17.7), extcorr=False, fluxfnout=None, onlyoutside=None):
    """
    Identifies flux calibration stars by choosing ~F stars based on color cuts.

    Uses the SDSS criteria for specphot standards:
    0.1 < (g-r) < 0.4

    their specphot stars are 16 < g < 17.1 and "reddening standards" are
    17.1 < g < 18.5

    `onlyoutside`, if not None, specifies that they should only be further from
    the given distance from the host. Should be an astropy quantity.
    """
    from astropy.units import degree, kpc

    starmsk = cat['type'] == 6 #type==6 means star
    cat = cat[starmsk]


    u = cat['u']
    g = cat['g']
    r = cat['r']
    if extcorr:
        u = u - cat['Au']
        g = g - cat['Ag']
        r = r - cat['Ar']
    umg = u - g
    gmr = g - r

    #msk = (0.1 < gmr) & (gmr < 0.4) #old version

    std_color = (0.6 < umg) & (umg < 1.2)
    std_color = std_color & (0.0 < gmr) & (gmr < 0.6)
    std_color = std_color & (gmr > 0.75 * umg - 0.45)

    sp_std = std_color & (15.5 < g) & (g < 17.0)
    red_std = std_color & (17 < g) & (g < 18.5)

    minmag = min(*magrng)
    maxmag = max(*magrng)

    msk = (sp_std|red_std) & (minmag < r)& (r < maxmag)

    if onlyoutside:
        if onlyoutside.unit.is_equivalent(degree):
            msk = msk & ((cat['rhost'] * degree) > onlyoutside)
        elif onlyoutside.unit.is_equivalent(kpc):
            msk = msk & (cat['rhost_kpc'] * kpc > onlyoutside)
        else:
            raise ValueError('onlyoutside is not an angle or length')


    if fluxfnout:
        names = 'RA DEC u_psf g_psf r_psf i_psf z_psf extinction_r'.split()
        dat = [cat[msk]['ra'],
               cat[msk]['dec'],
               cat[msk]['psf_u'],
               cat[msk]['psf_g'],
               cat[msk]['psf_r'],
               cat[msk]['psf_i'],
               cat[msk]['psf_z'],
               cat[msk]['Ar']
              ]
        tab = Table(data=dat, names=names)
        with open(fluxfnout, 'w') as f:
            #f.write('#RA DEC u_psf g_psf r_psf i_psf z_psf extinction_r')
            tab.write(f, format='ascii.commented_header')

    return cat[msk]
