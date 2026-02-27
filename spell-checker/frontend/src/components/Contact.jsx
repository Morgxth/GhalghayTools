import s from './Contact.module.css'

export default function Contact() {
  return (
    <div className={s.root}>
      <p className={s.lead}>
        Проект открытый — любые предложения, замечания и материалы приветствуются.
        Особенно ждём носителей языка и лингвистов.
      </p>

      <div className={s.cards}>
        <a
          className={s.card}
          href="https://github.com/Morgxth/ingush-spell-checker/issues"
          target="_blank"
          rel="noreferrer"
        >
          <div className={s.cardIcon}>⌥</div>
          <div>
            <div className={s.cardTitle}>Сообщить об ошибке</div>
            <div className={s.cardText}>
              Нашли неверную подсказку, пропущенное слово или баг в интерфейсе?
              Создайте issue на GitHub.
            </div>
            <div className={s.cardLink}>github.com/Morgxth/ingush-spell-checker →</div>
          </div>
        </a>

        <a
          className={s.card}
          href="https://github.com/Morgxth/ingush-spell-checker"
          target="_blank"
          rel="noreferrer"
        >
          <div className={s.cardIcon}>⎇</div>
          <div>
            <div className={s.cardTitle}>Внести вклад</div>
            <div className={s.cardText}>
              Репозиторий открыт для pull request-ов. Можно улучшать словарь,
              скрипты извлечения данных, стеммер или интерфейс.
            </div>
            <div className={s.cardLink}>Открыть репозиторий →</div>
          </div>
        </a>

        <a
          className={s.card}
          href="mailto:goygovs@gmail.com"
        >
          <div className={s.cardIcon}>✉</div>
          <div>
            <div className={s.cardTitle}>Написать напрямую</div>
            <div className={s.cardText}>
              Если вы лингвист, носитель языка или хотите передать словарные
              материалы — пишите на почту.
            </div>
            <div className={s.cardLink}>goygovs@gmail.com →</div>
          </div>
        </a>

        <div className={s.card}>
          <div className={s.cardIcon}>◈</div>
          <div>
            <div className={s.cardTitle}>Предложить перевод</div>
            <div className={s.cardText}>
              Если вы знаете перевод слова которого нет в словаре —
              воспользуйтесь формой в карточке слова на вкладке «Словарь».
              Предложение попадёт в очередь модерации.
            </div>
          </div>
        </div>
      </div>

      <div className={s.note}>
        <span className={s.noteIcon}>◎</span>
        Данные: словари Куркиева, Барахоевой, Кодзоева, Мерешкова, Оздоевой, Тариевой;
        корпус «Лоаман Іуйре» (1970–1990-е); грамматика Johanna Nichols (2011).
      </div>
    </div>
  )
}
