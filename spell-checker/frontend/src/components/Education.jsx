import s from './Education.module.css'

const planned = [
  {
    title: 'Тренажёр правописания',
    desc: 'Упражнения с пропущенными буквами, карточки слов для запоминания, прогресс по сессиям. Подходит для изучающих ингушский как второй язык.',
    status: 'planned',
  },
  {
    title: 'Примеры из корпуса',
    desc: 'Для каждого слова в словаре — реальные предложения из корпуса «Лоаман Іуйре», в которых оно встречается. Контекст помогает лучше понять значение.',
    status: 'planned',
  },
  {
    title: 'Морфологический разбор',
    desc: 'Разбор слова по морфемам: основа, падеж, число, часть речи. Наглядно показывает, как устроено ингушское слово.',
    status: 'planned',
  },
  {
    title: 'Интерактивная таблица падежей',
    desc: 'Склонение любого слова по всем 8 падежам в единственном и множественном числе — с переводами и примерами.',
    status: 'planned',
  },
  {
    title: 'Глоссарий терминов',
    desc: 'Тематические словари: административная лексика, медицина, природа, родство. Карточки с произношением (транскрипция).',
    status: 'planned',
  },
]

export default function Education() {
  return (
    <div className={s.root}>
      <div className={s.banner}>
        <div className={s.bannerIcon}>◎</div>
        <div>
          <div className={s.bannerTitle}>Раздел в разработке</div>
          <div className={s.bannerText}>
            Образовательная платформа для изучения ингушского языка. Здесь появятся
            упражнения, тренажёры и инструменты для работы с морфологией.
          </div>
        </div>
      </div>

      <h2 className={s.sectionTitle}>Запланировано</h2>
      <div className={s.list}>
        {planned.map((item) => (
          <div key={item.title} className={s.item}>
            <div className={s.itemHeader}>
              <span className={s.itemTitle}>{item.title}</span>
              <span className={s.badge}>скоро</span>
            </div>
            <p className={s.itemDesc}>{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
