import type { Bibliography, BibliographyAuthor } from "../types";

export type CitationStyle = "apa" | "mla" | "chicago" | "gbt7714" | "bibtex";
export type InTextCitationStyle =
  | "apa"
  | "mla"
  | "chicago"
  | "gbt7714"
  | "numeric";

/**
 * Format a single author name for APA style
 * APA: LastName, F. M.
 */
function formatAuthorAPA(author: BibliographyAuthor): string {
  if (author.literal) {
    return author.literal;
  }
  const family = author.family || "";
  const given = author.given || "";
  if (!family) return given;
  if (!given) return family;
  // Get initials from given name
  const initials = given
    .split(/\s+/)
    .map((n) => n.charAt(0).toUpperCase() + ".")
    .join(" ");
  return `${family}, ${initials}`;
}

/**
 * Format authors list for APA style
 * APA 7th: Up to 20 authors, use & before last author
 */
function formatAuthorsAPA(authors: BibliographyAuthor[]): string {
  if (!authors || authors.length === 0) return "";
  if (authors.length === 1) {
    return formatAuthorAPA(authors[0]);
  }
  if (authors.length === 2) {
    return `${formatAuthorAPA(authors[0])} & ${formatAuthorAPA(authors[1])}`;
  }
  if (authors.length <= 20) {
    const allButLast = authors.slice(0, -1).map(formatAuthorAPA).join(", ");
    return `${allButLast}, & ${formatAuthorAPA(authors[authors.length - 1])}`;
  }
  // More than 20 authors: first 19, ..., last author
  const first19 = authors.slice(0, 19).map(formatAuthorAPA).join(", ");
  return `${first19}, ... ${formatAuthorAPA(authors[authors.length - 1])}`;
}

/**
 * Format a single author name for MLA style
 * MLA: LastName, FirstName MiddleName
 */
function formatAuthorMLA(author: BibliographyAuthor, isFirst: boolean): string {
  if (author.literal) {
    return author.literal;
  }
  const family = author.family || "";
  const given = author.given || "";
  if (!family) return given;
  if (!given) return family;
  // First author: Last, First. Others: First Last
  if (isFirst) {
    return `${family}, ${given}`;
  }
  return `${given} ${family}`;
}

/**
 * Format authors list for MLA style
 * MLA 9th: 1 author, 2 authors with "and", 3+ use "et al."
 */
function formatAuthorsMLA(authors: BibliographyAuthor[]): string {
  if (!authors || authors.length === 0) return "";
  if (authors.length === 1) {
    return formatAuthorMLA(authors[0], true);
  }
  if (authors.length === 2) {
    return `${formatAuthorMLA(authors[0], true)}, and ${formatAuthorMLA(authors[1], false)}`;
  }
  // 3+ authors: first author et al.
  return `${formatAuthorMLA(authors[0], true)}, et al.`;
}

/**
 * Format a single author name for Chicago style
 * Chicago: FirstName LastName (for notes) or LastName, FirstName (for bibliography)
 */
function formatAuthorChicago(
  author: BibliographyAuthor,
  isFirst: boolean,
): string {
  if (author.literal) {
    return author.literal;
  }
  const family = author.family || "";
  const given = author.given || "";
  if (!family) return given;
  if (!given) return family;
  if (isFirst) {
    return `${family}, ${given}`;
  }
  return `${given} ${family}`;
}

/**
 * Format authors list for Chicago style
 * Chicago 17th (bibliography): Up to 10, then et al.
 */
function formatAuthorsChicago(authors: BibliographyAuthor[]): string {
  if (!authors || authors.length === 0) return "";
  if (authors.length === 1) {
    return formatAuthorChicago(authors[0], true);
  }
  if (authors.length === 2) {
    return `${formatAuthorChicago(authors[0], true)} and ${formatAuthorChicago(authors[1], false)}`;
  }
  if (authors.length === 3) {
    return `${formatAuthorChicago(authors[0], true)}, ${formatAuthorChicago(authors[1], false)}, and ${formatAuthorChicago(authors[2], false)}`;
  }
  if (authors.length <= 10) {
    const allButLast = authors
      .slice(0, -1)
      .map((a, i) => formatAuthorChicago(a, i === 0))
      .join(", ");
    return `${allButLast}, and ${formatAuthorChicago(authors[authors.length - 1], false)}`;
  }
  // More than 10: first 7 + et al.
  const first7 = authors
    .slice(0, 7)
    .map((a, i) => formatAuthorChicago(a, i === 0))
    .join(", ");
  return `${first7}, et al.`;
}

/**
 * Format citation in APA 7th edition style
 * Journal: Author, A. A., & Author, B. B. (Year). Title. *Journal*, *Vol*(Issue), Pages. doi
 * Book: Author, A. A. (Year). *Title*. Publisher.
 */
export function formatCitationAPA(bib: Bibliography): string {
  const parts: string[] = [];

  // Authors
  const authors = formatAuthorsAPA(bib.authors || []);
  if (authors) {
    parts.push(authors);
  }

  // Year
  if (bib.year) {
    parts.push(`(${bib.year})`);
  }

  // Combine author and year with space, add period
  let citation = parts.join(" ");
  if (citation) citation += ". ";

  // Title (italicized for books, not for articles)
  const isJournal = bib.docType === "J" || bib.journal;
  const title = bib.title || "";
  const subtitle = bib.subtitle ? `: ${bib.subtitle}` : "";
  const fullTitle = title + subtitle;

  if (fullTitle) {
    if (isJournal) {
      // Article titles are not italicized
      citation += fullTitle + ". ";
    } else {
      // Book titles are italicized
      citation += `*${fullTitle}*. `;
    }
  }

  // Journal info
  if (bib.journal) {
    let journalPart = `*${bib.journal}*`;
    if (bib.volume) {
      journalPart += `, *${bib.volume}*`;
      if (bib.issue) {
        journalPart += `(${bib.issue})`;
      }
    }
    if (bib.pages) {
      journalPart += `, ${bib.pages}`;
    }
    citation += journalPart + ". ";
  }

  // Publisher (for books)
  if (!isJournal && bib.publisher) {
    citation += bib.publisher + ". ";
  }

  // DOI
  if (bib.doi) {
    citation += `https://doi.org/${bib.doi}`;
  }

  return citation.trim();
}

/**
 * Format citation in MLA 9th edition style
 * Journal: Author. "Title." *Journal*, vol. X, no. Y, Year, pp. Pages.
 * Book: Author. *Title*. Publisher, Year.
 */
export function formatCitationMLA(bib: Bibliography): string {
  const parts: string[] = [];

  // Authors
  const authors = formatAuthorsMLA(bib.authors || []);
  if (authors) {
    parts.push(authors + ".");
  }

  // Title
  const isJournal = bib.docType === "J" || bib.journal;
  const title = bib.title || "";
  const subtitle = bib.subtitle ? `: ${bib.subtitle}` : "";
  const fullTitle = title + subtitle;

  if (fullTitle) {
    if (isJournal) {
      // Article titles in quotes
      parts.push(`"${fullTitle}."`);
    } else {
      // Book titles italicized
      parts.push(`*${fullTitle}*.`);
    }
  }

  // Journal info
  if (bib.journal) {
    let journalPart = `*${bib.journal}*`;
    if (bib.volume) {
      journalPart += `, vol. ${bib.volume}`;
    }
    if (bib.issue) {
      journalPart += `, no. ${bib.issue}`;
    }
    if (bib.year) {
      journalPart += `, ${bib.year}`;
    }
    if (bib.pages) {
      journalPart += `, pp. ${bib.pages}`;
    }
    parts.push(journalPart + ".");
  } else {
    // Book: Publisher, Year
    if (bib.publisher) {
      let pubPart = bib.publisher;
      if (bib.year) {
        pubPart += `, ${bib.year}`;
      }
      parts.push(pubPart + ".");
    } else if (bib.year) {
      parts.push(`${bib.year}.`);
    }
  }

  return parts.join(" ").trim();
}

/**
 * Format citation in Chicago 17th edition style (Notes-Bibliography)
 * Journal: Author, "Title," *Journal* Vol, no. Issue (Year): Pages.
 * Book: Author. *Title*. Place: Publisher, Year.
 */
export function formatCitationChicago(bib: Bibliography): string {
  const isJournal = bib.docType === "J" || bib.journal;

  // Authors
  const authors = formatAuthorsChicago(bib.authors || []);

  // Title
  const title = bib.title || "";
  const subtitle = bib.subtitle ? `: ${bib.subtitle}` : "";
  const fullTitle = title + subtitle;

  if (isJournal) {
    // Journal article format
    let citation = "";
    if (authors) {
      citation += authors + ". ";
    }
    if (fullTitle) {
      citation += `"${fullTitle}." `;
    }
    if (bib.journal) {
      citation += `*${bib.journal}*`;
      if (bib.volume) {
        citation += ` ${bib.volume}`;
      }
      if (bib.issue) {
        citation += `, no. ${bib.issue}`;
      }
      if (bib.year) {
        citation += ` (${bib.year})`;
      }
      if (bib.pages) {
        citation += `: ${bib.pages}`;
      }
      citation += ".";
    }
    if (bib.doi) {
      citation += ` https://doi.org/${bib.doi}.`;
    }
    return citation.trim();
  } else {
    // Book format
    let citation = "";
    if (authors) {
      citation += authors + ". ";
    }
    if (fullTitle) {
      citation += `*${fullTitle}*. `;
    }
    if (bib.place && bib.publisher) {
      citation += `${bib.place}: ${bib.publisher}`;
    } else if (bib.publisher) {
      citation += bib.publisher;
    }
    if (bib.year) {
      citation += `, ${bib.year}`;
    }
    citation += ".";
    return citation.trim();
  }
}

/**
 * Check if a name appears to be Chinese (contains CJK characters)
 */
function isCJKName(name: string): boolean {
  return /[\u4e00-\u9fff]/.test(name);
}

/**
 * Format a single author name for GB/T 7714-2015 style
 * Chinese: 姓名 (no comma)
 * Western: FAMILY G N (family uppercase, given as initials)
 */
function formatAuthorGBT7714(author: BibliographyAuthor): string {
  if (author.literal) {
    // Check if Chinese name
    if (isCJKName(author.literal)) {
      return author.literal;
    }
    // Western literal name - try to parse and format
    return author.literal.toUpperCase();
  }

  const family = author.family || "";
  const given = author.given || "";

  if (!family && !given) return "";
  if (!family) return given;
  if (!given) return family;

  // Check if Chinese name
  if (isCJKName(family) || isCJKName(given)) {
    return `${family}${given}`;
  }

  // Western name: FAMILY G N (initials without periods per GB/T 7714)
  const initials = given
    .split(/\s+/)
    .map((n) => n.charAt(0).toUpperCase())
    .join(" ");
  return `${family.toUpperCase()} ${initials}`;
}

/**
 * Format authors list for GB/T 7714-2015 style
 * Rules:
 * - ≤3 authors: list all
 * - >3 authors: first 3, then ",等" (Chinese) or ",et al" (Western)
 * - Separate authors with comma
 */
function formatAuthorsGBT7714(authors: BibliographyAuthor[]): string {
  if (!authors || authors.length === 0) return "";

  // Determine if primarily Chinese authors
  const hasChinese = authors.some((a) => {
    if (a.literal) return isCJKName(a.literal);
    return isCJKName(a.family || "") || isCJKName(a.given || "");
  });

  if (authors.length <= 3) {
    return authors.map(formatAuthorGBT7714).join(", ");
  }

  // More than 3 authors: first 3 + et al/等
  const first3 = authors.slice(0, 3).map(formatAuthorGBT7714).join(", ");
  return hasChinese ? `${first3}, 等` : `${first3}, et al`;
}

/**
 * Get document type marker for GB/T 7714-2015
 * Returns [J], [M], [D], etc.
 */
function getGBT7714TypeMarker(
  docType?: string | null,
  isOnline?: boolean,
): string {
  const typeMap: Record<string, string> = {
    J: "J", // 期刊
    M: "M", // 图书/专著
    C: "C", // 会议录
    G: "G", // 汇编
    N: "N", // 报纸
    D: "D", // 学位论文
    R: "R", // 报告
    S: "S", // 标准
    P: "P", // 专利
    DB: "DB", // 数据库
    CP: "CP", // 计算机程序
    EB: "EB", // 电子公告
    A: "A", // 档案
    CM: "CM", // 舆图
    DS: "DS", // 数据集
  };

  const type = typeMap[docType || ""] || "Z";
  // Add /OL suffix for online resources if URL/DOI present
  return isOnline ? `${type}/OL` : type;
}

/**
 * Format citation in GB/T 7714-2015 style (顺序编码制)
 *
 * Journal article [J]: 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
 * Book [M]: 作者. 书名[M]. 版本项. 出版地: 出版者, 年: 页码.
 * Dissertation [D]: 作者. 题名[D]. 地点: 学校, 年.
 * Report [R]: 作者. 题名[R]. 出版地: 出版者, 年.
 * Online [/OL]: 添加 [引用日期]. URL. DOI.
 */
export function formatCitationGBT7714(bib: Bibliography): string {
  const parts: string[] = [];
  const isOnline = !!(bib.url || bib.doi);
  const typeMarker = getGBT7714TypeMarker(bib.docType, isOnline);

  // Authors
  const authors = formatAuthorsGBT7714(bib.authors || []);
  if (authors) {
    parts.push(authors);
  }

  // Title with type marker
  const title = bib.title || "";
  const subtitle = bib.subtitle ? `: ${bib.subtitle}` : "";
  const fullTitle = title + subtitle;

  if (fullTitle) {
    parts.push(`${fullTitle}[${typeMarker}]`);
  } else {
    // If no title, still need the type marker
    parts.push(`[${typeMarker}]`);
  }

  // Join author and title with period
  let citation = parts.join(". ");
  if (citation && !citation.endsWith(".")) {
    citation += ". ";
  } else if (citation) {
    citation += " ";
  }

  const isJournal = bib.docType === "J" || bib.journal;
  const isDissertation = bib.docType === "D";

  if (isJournal && bib.journal) {
    // Journal format: 刊名, 年, 卷(期): 页码
    let journalPart = bib.journal;
    if (bib.year) {
      journalPart += `, ${bib.year}`;
    }
    if (bib.volume) {
      journalPart += `, ${bib.volume}`;
    }
    if (bib.issue) {
      journalPart += `(${bib.issue})`;
    }
    if (bib.pages) {
      journalPart += `: ${bib.pages}`;
    }
    citation += journalPart;
  } else if (isDissertation) {
    // Dissertation format: 地点: 学校, 年
    if (bib.place && bib.publisher) {
      citation += `${bib.place}: ${bib.publisher}`;
    } else if (bib.publisher) {
      citation += bib.publisher;
    }
    if (bib.year) {
      citation += `, ${bib.year}`;
    }
  } else {
    // Book/other format: 出版地: 出版者, 年: 页码
    if (bib.place && bib.publisher) {
      citation += `${bib.place}: ${bib.publisher}`;
    } else if (bib.publisher) {
      citation += bib.publisher;
    }
    if (bib.year) {
      citation += `, ${bib.year}`;
    }
    if (bib.pages) {
      citation += `: ${bib.pages}`;
    }
  }

  // Online resources: add access date and URL
  if (isOnline) {
    // Access date - use current date if not specified
    const today = new Date();
    const accessDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    citation += `[${accessDate}]`;

    if (bib.url) {
      citation += `. ${bib.url}`;
    }
    if (bib.doi && !bib.url?.includes(bib.doi)) {
      citation += `. DOI:${bib.doi}`;
    }
  }

  // Ensure ends with period
  citation = citation.trim();
  if (citation && !citation.endsWith(".")) {
    citation += ".";
  }

  return citation;
}

/**
 * Generate a BibTeX key from author and year
 */
function generateBibTeXKey(bib: Bibliography, relPath: string): string {
  let key = "";

  // Get first author's last name
  if (bib.authors && bib.authors.length > 0) {
    const firstAuthor = bib.authors[0];
    if (firstAuthor.literal) {
      // For Chinese names, use first character(s)
      key = firstAuthor.literal.replace(/\s+/g, "").slice(0, 10);
    } else if (firstAuthor.family) {
      key = firstAuthor.family.toLowerCase().replace(/\s+/g, "");
    }
  }

  // Add year
  if (bib.year) {
    key += bib.year.toString();
  }

  // Fallback to filename if no key generated
  if (!key) {
    key = relPath.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9]/g, "_");
  }

  // Sanitize key: only alphanumeric and underscores
  return key.replace(/[^a-zA-Z0-9_]/g, "");
}

/**
 * Format a single author for BibTeX
 */
function formatAuthorBibTeX(author: BibliographyAuthor): string {
  if (author.literal) {
    return `{${author.literal}}`;
  }
  const family = author.family || "";
  const given = author.given || "";
  if (!family && !given) return "";
  if (!family) return given;
  if (!given) return family;
  return `${family}, ${given}`;
}

/**
 * Format citation in BibTeX format
 */
export function formatBibTeX(bib: Bibliography, relPath: string): string {
  const entryType = getEntryType(bib.docType);
  const key = generateBibTeXKey(bib, relPath);

  const fields: string[] = [];

  // Authors
  if (bib.authors && bib.authors.length > 0) {
    const authorStr = bib.authors
      .map(formatAuthorBibTeX)
      .filter(Boolean)
      .join(" and ");
    if (authorStr) {
      fields.push(`  author = {${authorStr}}`);
    }
  }

  // Title
  if (bib.title) {
    const fullTitle = bib.subtitle
      ? `${bib.title}: ${bib.subtitle}`
      : bib.title;
    fields.push(`  title = {${fullTitle}}`);
  }

  // Journal
  if (bib.journal) {
    fields.push(`  journal = {${bib.journal}}`);
  }

  // Year
  if (bib.year) {
    fields.push(`  year = {${bib.year}}`);
  }

  // Volume
  if (bib.volume) {
    fields.push(`  volume = {${bib.volume}}`);
  }

  // Issue/Number
  if (bib.issue) {
    fields.push(`  number = {${bib.issue}}`);
  }

  // Pages
  if (bib.pages) {
    fields.push(`  pages = {${bib.pages}}`);
  }

  // Publisher
  if (bib.publisher) {
    fields.push(`  publisher = {${bib.publisher}}`);
  }

  // Address/Place
  if (bib.place) {
    fields.push(`  address = {${bib.place}}`);
  }

  // DOI
  if (bib.doi) {
    fields.push(`  doi = {${bib.doi}}`);
  }

  // URL
  if (bib.url) {
    fields.push(`  url = {${bib.url}}`);
  }

  return `@${entryType}{${key},\n${fields.join(",\n")}\n}`;
}

/**
 * Get BibTeX entry type from document type
 */
function getEntryType(docType?: string | null): string {
  switch (docType) {
    case "J":
      return "article";
    case "M":
      return "book";
    case "C":
      return "inproceedings";
    case "D":
      return "phdthesis";
    case "P":
      return "patent";
    case "S":
      return "techreport";
    default:
      return "misc";
  }
}

/**
 * Format a citation in the specified style
 */
export function formatCitation(
  bib: Bibliography,
  style: CitationStyle,
  relPath?: string,
): string {
  switch (style) {
    case "apa":
      return formatCitationAPA(bib);
    case "mla":
      return formatCitationMLA(bib);
    case "chicago":
      return formatCitationChicago(bib);
    case "gbt7714":
      return formatCitationGBT7714(bib);
    case "bibtex":
      return formatBibTeX(bib, relPath || "unknown");
    default:
      return formatCitationAPA(bib);
  }
}

/**
 * Check if a bibliography entry has enough data for a meaningful citation
 */
export function hasCitationData(bib?: Bibliography | null): boolean {
  if (!bib) return false;
  // At minimum need a title or authors
  return !!(bib.title || (bib.authors && bib.authors.length > 0));
}

// =============================================================================
// In-Text Citation Formatters (for copy functionality)
// =============================================================================

/**
 * Get the first author's last name for in-text citations
 */
function getFirstAuthorLastName(authors?: BibliographyAuthor[]): string | null {
  if (!authors || authors.length === 0) return null;
  const first = authors[0];
  if (first.literal) return first.literal;
  return first.family || first.given || null;
}

/**
 * Format in-text citation for APA style
 * Format: (Author, Year) or (Author, Year, p. Page)
 * Examples: (Smith, 2023), (Smith, 2023, p. 15), (Smith & Jones, 2023)
 */
function formatInTextAPA(bib: Bibliography, page?: number | null): string {
  const authors = bib.authors || [];
  let authorPart = "";

  if (authors.length === 0) {
    // Fallback to title if no authors
    authorPart = bib.title
      ? `"${bib.title.slice(0, 30)}${bib.title.length > 30 ? "..." : ""}"`
      : "Unknown";
  } else if (authors.length === 1) {
    authorPart = getFirstAuthorLastName(authors) || "Unknown";
  } else if (authors.length === 2) {
    const first = getFirstAuthorLastName([authors[0]]) || "Unknown";
    const second = getFirstAuthorLastName([authors[1]]) || "Unknown";
    authorPart = `${first} & ${second}`;
  } else {
    authorPart = `${getFirstAuthorLastName(authors) || "Unknown"} et al.`;
  }

  const parts = [authorPart];
  if (bib.year) parts.push(String(bib.year));
  if (page) parts.push(`p. ${page}`);

  return `(${parts.join(", ")})`;
}

/**
 * Format in-text citation for MLA style
 * Format: (Author Page)
 * Examples: (Smith 15), (Smith and Jones 15)
 */
function formatInTextMLA(bib: Bibliography, page?: number | null): string {
  const authors = bib.authors || [];
  let authorPart = "";

  if (authors.length === 0) {
    authorPart = bib.title
      ? `"${bib.title.slice(0, 30)}${bib.title.length > 30 ? "..." : ""}"`
      : "Unknown";
  } else if (authors.length === 1) {
    authorPart = getFirstAuthorLastName(authors) || "Unknown";
  } else if (authors.length === 2) {
    const first = getFirstAuthorLastName([authors[0]]) || "Unknown";
    const second = getFirstAuthorLastName([authors[1]]) || "Unknown";
    authorPart = `${first} and ${second}`;
  } else {
    authorPart = `${getFirstAuthorLastName(authors) || "Unknown"} et al.`;
  }

  if (page) {
    return `(${authorPart} ${page})`;
  }
  return `(${authorPart})`;
}

/**
 * Format in-text citation for Chicago style
 * Format: (Author Year, Page)
 * Examples: (Smith 2023, 15), (Smith and Jones 2023, 15)
 */
function formatInTextChicago(bib: Bibliography, page?: number | null): string {
  const authors = bib.authors || [];
  let authorPart = "";

  if (authors.length === 0) {
    authorPart = bib.title
      ? `"${bib.title.slice(0, 30)}${bib.title.length > 30 ? "..." : ""}"`
      : "Unknown";
  } else if (authors.length === 1) {
    authorPart = getFirstAuthorLastName(authors) || "Unknown";
  } else if (authors.length === 2) {
    const first = getFirstAuthorLastName([authors[0]]) || "Unknown";
    const second = getFirstAuthorLastName([authors[1]]) || "Unknown";
    authorPart = `${first} and ${second}`;
  } else {
    authorPart = `${getFirstAuthorLastName(authors) || "Unknown"} et al.`;
  }

  let citation = authorPart;
  if (bib.year) citation += ` ${bib.year}`;
  if (page) citation += `, ${page}`;

  return `(${citation})`;
}

/**
 * Format in-text citation for GB/T 7714 style (numeric)
 * Format: [序号]
 * Example: [1]
 */
function formatInTextGBT7714(index: number): string {
  return `[${index}]`;
}

/**
 * Format in-text citation for Numeric style
 * Format: [n]
 * Example: [1]
 */
function formatInTextNumeric(index: number): string {
  return `[${index}]`;
}

/**
 * Format an in-text citation based on the specified style
 * @param bib - The bibliography data for the source
 * @param style - The citation style to use
 * @param index - The 1-based index of the citation (for numeric styles)
 * @param page - Optional page number
 */
export function formatInTextCitation(
  bib: Bibliography | null | undefined,
  style: InTextCitationStyle,
  index: number,
  page?: number | null,
): string {
  // For numeric styles or missing bibliography, use the index
  if (style === "numeric" || style === "gbt7714") {
    return style === "gbt7714"
      ? formatInTextGBT7714(index)
      : formatInTextNumeric(index);
  }

  // If no bibliography data, fall back to numeric
  if (!bib || !hasCitationData(bib)) {
    return `[${index}]`;
  }

  switch (style) {
    case "apa":
      return formatInTextAPA(bib, page);
    case "mla":
      return formatInTextMLA(bib, page);
    case "chicago":
      return formatInTextChicago(bib, page);
    default:
      return formatInTextAPA(bib, page);
  }
}
