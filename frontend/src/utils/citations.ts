import type { Bibliography, BibliographyAuthor } from '../types'

export type CitationStyle = 'apa' | 'mla' | 'chicago' | 'bibtex'

/**
 * Format a single author name for APA style
 * APA: LastName, F. M.
 */
function formatAuthorAPA(author: BibliographyAuthor): string {
  if (author.literal) {
    return author.literal
  }
  const family = author.family || ''
  const given = author.given || ''
  if (!family) return given
  if (!given) return family
  // Get initials from given name
  const initials = given.split(/\s+/).map(n => n.charAt(0).toUpperCase() + '.').join(' ')
  return `${family}, ${initials}`
}

/**
 * Format authors list for APA style
 * APA 7th: Up to 20 authors, use & before last author
 */
function formatAuthorsAPA(authors: BibliographyAuthor[]): string {
  if (!authors || authors.length === 0) return ''
  if (authors.length === 1) {
    return formatAuthorAPA(authors[0])
  }
  if (authors.length === 2) {
    return `${formatAuthorAPA(authors[0])} & ${formatAuthorAPA(authors[1])}`
  }
  if (authors.length <= 20) {
    const allButLast = authors.slice(0, -1).map(formatAuthorAPA).join(', ')
    return `${allButLast}, & ${formatAuthorAPA(authors[authors.length - 1])}`
  }
  // More than 20 authors: first 19, ..., last author
  const first19 = authors.slice(0, 19).map(formatAuthorAPA).join(', ')
  return `${first19}, ... ${formatAuthorAPA(authors[authors.length - 1])}`
}

/**
 * Format a single author name for MLA style
 * MLA: LastName, FirstName MiddleName
 */
function formatAuthorMLA(author: BibliographyAuthor, isFirst: boolean): string {
  if (author.literal) {
    return author.literal
  }
  const family = author.family || ''
  const given = author.given || ''
  if (!family) return given
  if (!given) return family
  // First author: Last, First. Others: First Last
  if (isFirst) {
    return `${family}, ${given}`
  }
  return `${given} ${family}`
}

/**
 * Format authors list for MLA style
 * MLA 9th: 1 author, 2 authors with "and", 3+ use "et al."
 */
function formatAuthorsMLA(authors: BibliographyAuthor[]): string {
  if (!authors || authors.length === 0) return ''
  if (authors.length === 1) {
    return formatAuthorMLA(authors[0], true)
  }
  if (authors.length === 2) {
    return `${formatAuthorMLA(authors[0], true)}, and ${formatAuthorMLA(authors[1], false)}`
  }
  // 3+ authors: first author et al.
  return `${formatAuthorMLA(authors[0], true)}, et al.`
}

/**
 * Format a single author name for Chicago style
 * Chicago: FirstName LastName (for notes) or LastName, FirstName (for bibliography)
 */
function formatAuthorChicago(author: BibliographyAuthor, isFirst: boolean): string {
  if (author.literal) {
    return author.literal
  }
  const family = author.family || ''
  const given = author.given || ''
  if (!family) return given
  if (!given) return family
  if (isFirst) {
    return `${family}, ${given}`
  }
  return `${given} ${family}`
}

/**
 * Format authors list for Chicago style
 * Chicago 17th (bibliography): Up to 10, then et al.
 */
function formatAuthorsChicago(authors: BibliographyAuthor[]): string {
  if (!authors || authors.length === 0) return ''
  if (authors.length === 1) {
    return formatAuthorChicago(authors[0], true)
  }
  if (authors.length === 2) {
    return `${formatAuthorChicago(authors[0], true)} and ${formatAuthorChicago(authors[1], false)}`
  }
  if (authors.length === 3) {
    return `${formatAuthorChicago(authors[0], true)}, ${formatAuthorChicago(authors[1], false)}, and ${formatAuthorChicago(authors[2], false)}`
  }
  if (authors.length <= 10) {
    const allButLast = authors.slice(0, -1).map((a, i) => formatAuthorChicago(a, i === 0)).join(', ')
    return `${allButLast}, and ${formatAuthorChicago(authors[authors.length - 1], false)}`
  }
  // More than 10: first 7 + et al.
  const first7 = authors.slice(0, 7).map((a, i) => formatAuthorChicago(a, i === 0)).join(', ')
  return `${first7}, et al.`
}

/**
 * Format citation in APA 7th edition style
 * Journal: Author, A. A., & Author, B. B. (Year). Title. *Journal*, *Vol*(Issue), Pages. doi
 * Book: Author, A. A. (Year). *Title*. Publisher.
 */
export function formatCitationAPA(bib: Bibliography): string {
  const parts: string[] = []

  // Authors
  const authors = formatAuthorsAPA(bib.authors || [])
  if (authors) {
    parts.push(authors)
  }

  // Year
  if (bib.year) {
    parts.push(`(${bib.year})`)
  }

  // Combine author and year with space, add period
  let citation = parts.join(' ')
  if (citation) citation += '. '

  // Title (italicized for books, not for articles)
  const isJournal = bib.docType === 'J' || bib.journal
  const title = bib.title || ''
  const subtitle = bib.subtitle ? `: ${bib.subtitle}` : ''
  const fullTitle = title + subtitle

  if (fullTitle) {
    if (isJournal) {
      // Article titles are not italicized
      citation += fullTitle + '. '
    } else {
      // Book titles are italicized
      citation += `*${fullTitle}*. `
    }
  }

  // Journal info
  if (bib.journal) {
    let journalPart = `*${bib.journal}*`
    if (bib.volume) {
      journalPart += `, *${bib.volume}*`
      if (bib.issue) {
        journalPart += `(${bib.issue})`
      }
    }
    if (bib.pages) {
      journalPart += `, ${bib.pages}`
    }
    citation += journalPart + '. '
  }

  // Publisher (for books)
  if (!isJournal && bib.publisher) {
    citation += bib.publisher + '. '
  }

  // DOI
  if (bib.doi) {
    citation += `https://doi.org/${bib.doi}`
  }

  return citation.trim()
}

/**
 * Format citation in MLA 9th edition style
 * Journal: Author. "Title." *Journal*, vol. X, no. Y, Year, pp. Pages.
 * Book: Author. *Title*. Publisher, Year.
 */
export function formatCitationMLA(bib: Bibliography): string {
  const parts: string[] = []

  // Authors
  const authors = formatAuthorsMLA(bib.authors || [])
  if (authors) {
    parts.push(authors + '.')
  }

  // Title
  const isJournal = bib.docType === 'J' || bib.journal
  const title = bib.title || ''
  const subtitle = bib.subtitle ? `: ${bib.subtitle}` : ''
  const fullTitle = title + subtitle

  if (fullTitle) {
    if (isJournal) {
      // Article titles in quotes
      parts.push(`"${fullTitle}."`)
    } else {
      // Book titles italicized
      parts.push(`*${fullTitle}*.`)
    }
  }

  // Journal info
  if (bib.journal) {
    let journalPart = `*${bib.journal}*`
    if (bib.volume) {
      journalPart += `, vol. ${bib.volume}`
    }
    if (bib.issue) {
      journalPart += `, no. ${bib.issue}`
    }
    if (bib.year) {
      journalPart += `, ${bib.year}`
    }
    if (bib.pages) {
      journalPart += `, pp. ${bib.pages}`
    }
    parts.push(journalPart + '.')
  } else {
    // Book: Publisher, Year
    if (bib.publisher) {
      let pubPart = bib.publisher
      if (bib.year) {
        pubPart += `, ${bib.year}`
      }
      parts.push(pubPart + '.')
    } else if (bib.year) {
      parts.push(`${bib.year}.`)
    }
  }

  return parts.join(' ').trim()
}

/**
 * Format citation in Chicago 17th edition style (Notes-Bibliography)
 * Journal: Author, "Title," *Journal* Vol, no. Issue (Year): Pages.
 * Book: Author. *Title*. Place: Publisher, Year.
 */
export function formatCitationChicago(bib: Bibliography): string {
  const isJournal = bib.docType === 'J' || bib.journal

  // Authors
  const authors = formatAuthorsChicago(bib.authors || [])

  // Title
  const title = bib.title || ''
  const subtitle = bib.subtitle ? `: ${bib.subtitle}` : ''
  const fullTitle = title + subtitle

  if (isJournal) {
    // Journal article format
    let citation = ''
    if (authors) {
      citation += authors + '. '
    }
    if (fullTitle) {
      citation += `"${fullTitle}." `
    }
    if (bib.journal) {
      citation += `*${bib.journal}*`
      if (bib.volume) {
        citation += ` ${bib.volume}`
      }
      if (bib.issue) {
        citation += `, no. ${bib.issue}`
      }
      if (bib.year) {
        citation += ` (${bib.year})`
      }
      if (bib.pages) {
        citation += `: ${bib.pages}`
      }
      citation += '.'
    }
    if (bib.doi) {
      citation += ` https://doi.org/${bib.doi}.`
    }
    return citation.trim()
  } else {
    // Book format
    let citation = ''
    if (authors) {
      citation += authors + '. '
    }
    if (fullTitle) {
      citation += `*${fullTitle}*. `
    }
    if (bib.place && bib.publisher) {
      citation += `${bib.place}: ${bib.publisher}`
    } else if (bib.publisher) {
      citation += bib.publisher
    }
    if (bib.year) {
      citation += `, ${bib.year}`
    }
    citation += '.'
    return citation.trim()
  }
}

/**
 * Generate a BibTeX key from author and year
 */
function generateBibTeXKey(bib: Bibliography, relPath: string): string {
  let key = ''

  // Get first author's last name
  if (bib.authors && bib.authors.length > 0) {
    const firstAuthor = bib.authors[0]
    if (firstAuthor.literal) {
      // For Chinese names, use first character(s)
      key = firstAuthor.literal.replace(/\s+/g, '').slice(0, 10)
    } else if (firstAuthor.family) {
      key = firstAuthor.family.toLowerCase().replace(/\s+/g, '')
    }
  }

  // Add year
  if (bib.year) {
    key += bib.year.toString()
  }

  // Fallback to filename if no key generated
  if (!key) {
    key = relPath.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9]/g, '_')
  }

  // Sanitize key: only alphanumeric and underscores
  return key.replace(/[^a-zA-Z0-9_]/g, '')
}

/**
 * Format a single author for BibTeX
 */
function formatAuthorBibTeX(author: BibliographyAuthor): string {
  if (author.literal) {
    return `{${author.literal}}`
  }
  const family = author.family || ''
  const given = author.given || ''
  if (!family && !given) return ''
  if (!family) return given
  if (!given) return family
  return `${family}, ${given}`
}

/**
 * Format citation in BibTeX format
 */
export function formatBibTeX(bib: Bibliography, relPath: string): string {
  const entryType = getEntryType(bib.docType)
  const key = generateBibTeXKey(bib, relPath)

  const fields: string[] = []

  // Authors
  if (bib.authors && bib.authors.length > 0) {
    const authorStr = bib.authors.map(formatAuthorBibTeX).filter(Boolean).join(' and ')
    if (authorStr) {
      fields.push(`  author = {${authorStr}}`)
    }
  }

  // Title
  if (bib.title) {
    const fullTitle = bib.subtitle ? `${bib.title}: ${bib.subtitle}` : bib.title
    fields.push(`  title = {${fullTitle}}`)
  }

  // Journal
  if (bib.journal) {
    fields.push(`  journal = {${bib.journal}}`)
  }

  // Year
  if (bib.year) {
    fields.push(`  year = {${bib.year}}`)
  }

  // Volume
  if (bib.volume) {
    fields.push(`  volume = {${bib.volume}}`)
  }

  // Issue/Number
  if (bib.issue) {
    fields.push(`  number = {${bib.issue}}`)
  }

  // Pages
  if (bib.pages) {
    fields.push(`  pages = {${bib.pages}}`)
  }

  // Publisher
  if (bib.publisher) {
    fields.push(`  publisher = {${bib.publisher}}`)
  }

  // Address/Place
  if (bib.place) {
    fields.push(`  address = {${bib.place}}`)
  }

  // DOI
  if (bib.doi) {
    fields.push(`  doi = {${bib.doi}}`)
  }

  // URL
  if (bib.url) {
    fields.push(`  url = {${bib.url}}`)
  }

  return `@${entryType}{${key},\n${fields.join(',\n')}\n}`
}

/**
 * Get BibTeX entry type from document type
 */
function getEntryType(docType?: string | null): string {
  switch (docType) {
    case 'J':
      return 'article'
    case 'M':
      return 'book'
    case 'C':
      return 'inproceedings'
    case 'D':
      return 'phdthesis'
    case 'P':
      return 'patent'
    case 'S':
      return 'techreport'
    default:
      return 'misc'
  }
}

/**
 * Format a citation in the specified style
 */
export function formatCitation(bib: Bibliography, style: CitationStyle, relPath?: string): string {
  switch (style) {
    case 'apa':
      return formatCitationAPA(bib)
    case 'mla':
      return formatCitationMLA(bib)
    case 'chicago':
      return formatCitationChicago(bib)
    case 'bibtex':
      return formatBibTeX(bib, relPath || 'unknown')
    default:
      return formatCitationAPA(bib)
  }
}

/**
 * Check if a bibliography entry has enough data for a meaningful citation
 */
export function hasCitationData(bib?: Bibliography | null): boolean {
  if (!bib) return false
  // At minimum need a title or authors
  return !!(bib.title || (bib.authors && bib.authors.length > 0))
}
